"""Main interface for evolving applications."""

from __future__ import unicode_literals

import os
from collections import OrderedDict
from importlib import import_module

from django.db import connections, transaction
from django.db.utils import DEFAULT_DB_ALIAS
from django.utils import six
from django.utils.translation import ugettext as _

from django_evolution.builtin_evolutions import BUILTIN_SEQUENCES
from django_evolution.compat.apps import get_apps
from django_evolution.db.state import DatabaseState
from django_evolution.diff import Diff
from django_evolution.errors import (EvolutionBaselineMissingError,
                                     EvolutionException,
                                     EvolutionTaskAlreadyQueuedError,
                                     EvolutionExecutionError,
                                     QueueEvolverTaskError)
from django_evolution.models import Evolution, Version
from django_evolution.mutations import (AddField,
                                        DeleteApplication,
                                        RenameModel,
                                        SQLMutation)
from django_evolution.mutators import AppMutator
from django_evolution.signals import applied_evolution, applying_evolution
from django_evolution.signature import ProjectSignature
from django_evolution.utils import execute_sql, get_app_label, get_app_name


class BaseEvolutionTask(object):
    """Base class for a task to perform during evolution.

    Attributes:
        can_simulate (bool):
            Whether the task can be simulated without requiring additional
            information.

            This is set after calling :py:meth:`prepare`.

        evolution_required (bool):
            Whether an evolution is required by this task.

            This is set after calling :py:meth:`prepare`.

        evolver (Evolver):
            The evolver that will execute the task.

        id (unicode):
            The unique ID for the task.

        new_evolutions (list of django_evolution.models.Evolution):
            A list of evolution model entries this task would create.

            This is set after calling :py:meth:`prepare`.

        sql (list):
            A list of SQL statements to perform for the task. Each entry can
            be a string or tuple accepted by
            :py:func:`~django_evolution.utils.execute_sql`.
    """

    def __init__(self, task_id, evolver):
        """Initialize the task.

        Args:
            task_id (unicode):
                The unique ID for the task.

            evolver (Evolver):
                The evolver that will execute the task.
        """
        self.id = task_id
        self.evolver = evolver

        self.can_simulate = False
        self.evolution_required = False
        self.new_evolutions = []
        self.sql = []

    def is_mutation_mutable(self, mutation, **kwargs):
        """Return whether a mutation is mutable.

        This is a handy wrapper around :py:meth:`BaseMutation.is_mutable
        <django_evolution.mutations.BaseMutation.is_mutable>` that passes
        standard arguments based on evolver state. Callers should pass any
        additional arguments that are required as keyword arguments.

        Args:
            mutation (django_evolution.mutations.BaseMutation):
                The mutation to check.

            **kwargs (dict):
                Additional keyword arguments to pass to
                :py:meth:`BaseMutation.is_mutable
                <django_evolution.mutations.BaseMutation.is_mutable>`.

        Returns:
            bool:
            ``True`` if the mutation is mutable. ``False`` if it is not.
        """
        evolver = self.evolver

        return mutation.is_mutable(project_sig=evolver.project_sig,
                                   database_state=evolver.database_state,
                                   database=evolver.database_name,
                                   **kwargs)

    def prepare(self, hinted, **kwargs):
        """Prepare state for this task.

        This is responsible for determining whether the task applies to the
        database. It must set :py:attr:`evolution_required`,
        :py:attr:`new_evolutions`, and :py:attr:`sql`.

        This must be called before :py:meth:`execute` or
        :py:meth:`get_evolution_content`.

        Args:
            hinted (bool):
                Whether to prepare the task for hinted evolutions.

            **kwargs (dict, unused):
                Additional keyword arguments passed for task preparation.
                This is provide for future expansion purposes.
        """
        raise NotImplementedError

    def execute(self, cursor):
        """Execute the task.

        This will make any changes necessary to the database.

        Args:
            cursor (django.db.backends.util.CursorWrapper):
                The database cursor used to execute queries.

        Raises:
            django_evolution.errors.EvolutionExecutionError:
                The evolution task failed. Details are in the error.
        """
        raise NotImplementedError

    def get_evolution_content(self):
        """Return the content for an evolution file for this task.

        Returns:
            unicode:
            The evolution content.
        """
        raise NotImplementedError

    def __str__(self):
        """Return a string description of the task.

        Returns:
            unicode:
            The string description.
        """
        raise NotImplementedError


class PurgeAppTask(BaseEvolutionTask):
    """A task for purging an application's tables from the database.

    Attributes:
        app_label (unicode):
            The app label for the app to purge.
    """

    def __init__(self, evolver, app_label):
        """Initialize the task.

        Args:
            evolver (Evolver):
                The evolver that will execute the task.

            app_label (unicode):
                The app label for the app to purge.
        """
        super(PurgeAppTask, self).__init__(task_id='purge-app:%s' % app_label,
                                           evolver=evolver)

        self.app_label = app_label

    def prepare(self, **kwargs):
        """Prepare state for this task.

        This will determine if the app's tables need to be deleted from
        the database, and prepare the SQL for doing so.

        Args:
            **kwargs (dict, unused):
                Keyword arguments passed for task preparation.
        """
        evolver = self.evolver
        mutation = DeleteApplication()

        if self.is_mutation_mutable(mutation, app_label=self.app_label):
            app_mutator = AppMutator.from_evolver(evolver=evolver,
                                                  app_label=self.app_label)
            app_mutator.run_mutation(mutation)

            self.evolution_required = True
            self.sql = app_mutator.to_sql()

        self.can_simulate = True
        self.new_evolutions = []

    def execute(self, cursor):
        """Execute the task.

        This will delete any tables owned by the application.

        Args:
            cursor (django.db.backends.util.CursorWrapper):
                The database cursor used to execute queries.

        Raises:
            django_evolution.errors.EvolutionExecutionError:
                The evolution task failed. Details are in the error.
        """
        if self.evolution_required:
            try:
                execute_sql(cursor, self.sql, self.evolver.database_name)
            except Exception as e:
                raise EvolutionExecutionError(
                    _('Error purging app "%s": %s')
                    % (self.app_label, e),
                    app_label=self.app_label,
                    detailed_error=six.text_type(e),
                    last_sql_statement=getattr(e, 'last_sql_statement'))

    def __str__(self):
        """Return a string description of the task.

        Returns:
            unicode:
            The string description.
        """
        return 'Purge application "%s"' % self.app_label


class EvolveAppTask(BaseEvolutionTask):
    """A task for evolving models in an application.

    This task will run through any evolutions in the provided application and
    handle applying each of those evolutions that haven't yet been applied.

    Attributes:
        app (module):
            The app module to evolve.

        app_label (unicode):
            The app label for the app to evolve.
    """

    def __init__(self, evolver, app, evolutions=None):
        """Initialize the task.

        Args:
            evolver (Evolver):
                The evolver that will execute the task.

            app (module):
                The app module to evolve.

            evolutions (list of dict, optional):
                Optional evolutions to use for the app instead of loading
                from a file. This is intended for testing purposes.

                Each dictionary needs a ``label`` key for the evolution label
                and a ``mutations`` key for a list of
                :py:class:`~django_evolution.mutations.BaseMutation` instances.
        """
        super(EvolveAppTask, self).__init__(
            task_id='evolve-app:%s' % app.__name__,
            evolver=evolver)

        self.app_label = get_app_label(app)
        self.app = app
        self._evolutions = evolutions
        self._mutations = None

    def prepare(self, hinted, **kwargs):
        """Prepare state for this task.

        This will determine if there are any unapplied evolutions in the app,
        and record that state and the SQL needed to apply the evolutions.

        Args:
            hinted (bool):
                Whether to prepare the task for hinted evolutions.

            **kwargs (dict, unused):
                Additional keyword arguments passed for task preparation.
        """
        app = self.app
        app_label = self.app_label
        evolver = self.evolver
        database_name = evolver.database_name

        if self._evolutions is not None:
            evolutions = []
            pending_mutations = []

            for evolution in self._evolutions:
                evolutions.append(evolution['label'])
                pending_mutations += evolution['mutations']
        elif hinted:
            evolutions = []
            hinted_evolution = evolver.initial_diff.evolution()
            pending_mutations = hinted_evolution.get(self.app_label, [])
        else:
            evolutions = get_unapplied_evolutions(app=app,
                                                  database=database_name)
            pending_mutations = get_mutations(app=app,
                                              evolution_labels=evolutions,
                                              database=database_name)

        mutations = [
            mutation
            for mutation in pending_mutations
            if self.is_mutation_mutable(mutation, app_label=self.app_label)
        ]

        if mutations:
            app_mutator = AppMutator.from_evolver(evolver=evolver,
                                                  app_label=self.app_label)
            app_mutator.run_mutations(mutations)

            self.can_simulate = app_mutator.can_simulate
            self.sql = app_mutator.to_sql()
            self.evolution_required = True
            self.new_evolutions = [
                Evolution(app_label=app_label,
                          label=label)
                for label in evolutions
            ]
            self._mutations = mutations

    def execute(self, cursor):
        """Execute the task.

        This will apply any evolutions queued up for the app.

        Before the evolutions are applied for the app, the
        :py:data:`~django_evolution.signals.applying_evolution` signal will
        be emitted. After,
        :py:data:`~django_evolution.signals.applied_evolution` will be emitted.

        Args:
            cursor (django.db.backends.util.CursorWrapper):
                The database cursor used to execute queries.

        Raises:
            django_evolution.errors.EvolutionExecutionError:
                The evolution task failed. Details are in the error.
        """
        if self.evolution_required:
            applying_evolution.send(sender=self.evolver,
                                    task=self)

            try:
                execute_sql(cursor, self.sql, self.evolver.database_name)
            except Exception as e:
                raise EvolutionExecutionError(
                    _('Error applying evolution for %s: %s')
                    % (self.app_label, e),
                    app_label=self.app_label,
                    detailed_error=six.text_type(e),
                    last_sql_statement=getattr(e, 'last_sql_statement'))

            applied_evolution.send(sender=self.evolver,
                                   task=self)

    def get_evolution_content(self):
        """Return the content for an evolution file for this task.

        Returns:
            unicode:
            The evolution content.
        """
        if not self._mutations:
            return None

        imports = set()
        project_imports = set()
        mutation_types = set()
        mutation_lines = []

        app_prefix = self.app.__name__.split('.')[0]

        for mutation in self._mutations:
            mutation_types.add(type(mutation).__name__)
            mutation_lines.append('    %s,' % mutation)

            if isinstance(mutation, AddField):
                field_module = mutation.field_type.__module__

                if field_module.startswith('django.db.models'):
                    imports.add('from django.db import models')
                else:
                    import_str = ('from %s import %s' %
                                  (field_module, mutation.field_type.__name__))

                    if field_module.startswith(app_prefix):
                        project_imports.add(import_str)
                    else:
                        imports.add(import_str)

        imports.add('from django_evolution.mutations import %s'
                    % ', '.join(sorted(mutation_types)))

        lines = [
            'from __future__ import unicode_literals',
            '',
        ] + sorted(imports)

        lines.append('')

        if project_imports:
            lines += sorted(project_imports)
            lines.append('')

        lines += [
            '',
            'MUTATIONS = [',
        ] + mutation_lines + [
            ']',
        ]

        return '\n'.join(lines)

    def __str__(self):
        """Return a string description of the task.

        Returns:
            unicode:
            The string description.
        """
        return 'Evolve application "%s"' % self.app_label


class Evolver(object):
    """The main class for managing database evolutions.

    The evolver is used to queue up tasks that modify the database. These
    allow for evolving database models and purging applications across an
    entire Django project or only for specific applications. Custom tasks
    can even be written by an application if very specific database
    operations need to be made outside of what's available in an evolution.

    Callers are expected to create an instance and queue up one or more tasks.
    Once all tasks are queued, the changes can be made using :py:meth:`evolve`.
    Alternatively, evolution hints can be generated using
    :py:meth:`generate_hints`.

    Projects will generally utilize this through the existing ``evolve``
    Django management command.

    Attributes:
        database_name (unicode):
            The name of the database being evolved.

        database_state (django_evolution.db.state.DatabaseState):
            The state of the database, for evolution purposes.

        initial_diff (django_evolution.diff.Diff):
            The initial diff between the stored project signature and the
            current project signature.

        project_sig (django_evolution.signature.ProjectSignature):
            The project signature. This will start off as the previous
            signature stored in the database, but will be modified when
            mutations are simulated.
    """

    def __init__(self, hinted=False, database_name=DEFAULT_DB_ALIAS):
        """Initialize the evolver.

        Args:
            database_name (unicode, optional):
                The name of the database to evolve.

        Raises:
            django_evolution.errors.EvolutionBaselineMissingError:
                An initial baseline for the project was not yet installed.
                This is due to ``syncdb``/``migrate`` not having been run.
        """
        self.database_name = database_name
        self.hinted = hinted
        self.initial_diff = None
        self.database_state = None
        self.project_sig = None
        self.evolved = False

        self.database_state = DatabaseState(self.database_name)
        self._target_project_sig = \
            ProjectSignature.from_database(database_name)

        self._tasks = OrderedDict()
        self._tasks_prepared = False

        try:
            latest_version = \
                Version.objects.current_version(using=database_name)

            self.project_sig = latest_version.signature
            self.initial_diff = Diff(self.project_sig,
                                     self._target_project_sig)
        except Version.DoesNotExist:
            # TODO: Once we're automatically running syncdb/migrate, this
            #       shouldn't be an issue, and we can remove the error.
            #       Or make it something more dire.
            raise EvolutionBaselineMissingError(
                _('An evolution baseline must be set before an evolution '
                  'can be performed.'))

    @property
    def tasks(self):
        """A list of all tasks that will be performed.

        This can only be accessed after all necessary tasks have been queued.
        """
        # If a caller is interested in the list of tasks, then it's likely
        # interested in state on those tasks. That means we'll need to prepare
        # all the tasks before we can return any of them.
        self._prepare_tasks()

        return six.itervalues(self._tasks)

    def can_simulate(self):
        """Return whether all queued tasks can be simulated.

        If any tasks cannot be simulated (for instance, a hinted evolution
        requiring manually-entered values), then this will return ``False``.

        This can only be called after all tasks have been queued.

        Returns:
            bool:
            ``True`` if all queued tasks can be simulated. ``False`` if any
            cannot.
        """
        return all(
            task.can_simulate or not task.evolution_required
            for task in self.tasks
        )

    def get_evolution_required(self):
        """Return whether there are any evolutions required.

        This can only be called after all tasks have been queued.

        Returns:
            bool:
            ``True`` if any tasks require evolution. ``False`` if none do.
        """
        return any(
            task.evolution_required
            for task in self.tasks
        )

    def diff_evolutions(self):
        """Return a diff between stored and post-evolution project signatures.

        This will run through all queued tasks, preparing them and simulating
        their changes. The returned diff will represent the changes made in
        those tasks.

        This can only be called after all tasks have been queued.

        Returns:
            django_evolution.diff.Diff:
            The diff between the stored signature and the queued changes.
        """
        self._prepare_tasks()

        return Diff(self.project_sig, self._target_project_sig)

    def iter_evolution_content(self):
        """Generate the evolution content for all queued tasks.

        This will loop through each tasks and yield any evolution content
        provided.

        This can only be called after all tasks have been queued.

        Yields:
            tuple:
            A tuple of ``(task, evolution_content)``.
        """
        for task in self.tasks:
            content = task.get_evolution_content()

            if content:
                yield task, content

    def queue_evolve_all_apps(self):
        """Queue an evolution of all registered Django apps.

        This cannot be used if :py:meth:`queue_evolve_app` is also being used.

        Raises:
            django_evolution.errors.EvolutionTaskAlreadyQueuedError:
                An evolution for an app was already queued.

            django_evolution.errors.QueueEvolverTaskError:
                Error queueing a non-duplicate task. Tasks may have already
                been prepared and finalized.
        """
        for app in get_apps():
            self.queue_evolve_app(app)

    def queue_evolve_app(self, app):
        """Queue an evolution of a registered Django app.

        Args:
            app (module):
                The Django app to queue an evolution for.

        Raises:
            django_evolution.errors.EvolutionTaskAlreadyQueuedError:
                An evolution for this app was already queued.

            django_evolution.errors.QueueEvolverTaskError:
                Error queueing a non-duplicate task. Tasks may have already
                been prepared and finalized.
        """
        try:
            self.queue_task(EvolveAppTask(self, app))
        except EvolutionTaskAlreadyQueuedError:
            raise EvolutionTaskAlreadyQueuedError(
                _('"%s" is already being tracked for evolution')
                % get_app_label(app))

    def queue_purge_old_apps(self):
        """Queue the purging of all old, stale Django apps.

        This will purge any apps that exist in the stored project signature
        but that are no longer registered in Django.

        This generally should not be used if :py:meth:`queue_purge_app` is also
        being used.

        Raises:
            django_evolution.errors.EvolutionTaskAlreadyQueuedError:
                A purge of an app was already queued.

            django_evolution.errors.QueueEvolverTaskError:
                Error queueing a non-duplicate task. Tasks may have already
                been prepared and finalized.
        """
        for app_label in self.initial_diff.deleted:
            self.queue_purge_app(app_label)

    def queue_purge_app(self, app_label):
        """Queue the purging of a Django app.

        Args:
            app_label (unicode):
                The label of the app to purge.

        Raises:
            django_evolution.errors.EvolutionTaskAlreadyQueuedError:
                A purge of this app was already queued.

            django_evolution.errors.QueueEvolverTaskError:
                Error queueing a non-duplicate task. Tasks may have already
                been prepared and finalized.
        """
        try:
            self.queue_task(PurgeAppTask(self, app_label))
        except EvolutionTaskAlreadyQueuedError:
            raise EvolutionTaskAlreadyQueuedError(
                _('"%s" is already being tracked for purging')
                % app_label)

    def queue_task(self, task):
        """Queue a task to run during evolution.

        This should only be directly called if working with custom tasks.
        Otherwise, use a more specific queue method.

        Args:
            task (BaseEvolutionTask):
                The task to queue.

        Raises:
            django_evolution.errors.EvolutionTaskAlreadyQueuedError:
                A purge of this app was already queued.

            django_evolution.errors.QueueEvolverTaskError:
                Error queueing a non-duplicate task. Tasks may have already
                been prepared and finalized.

        """
        assert task.id

        if self._tasks_prepared:
            raise QueueEvolverTaskError(
                _('Evolution tasks have already been prepared. New tasks '
                  'cannot be added.'))

        if task.id in self._tasks:
            raise EvolutionTaskAlreadyQueuedError(
                _('A task with ID "%s" is already queued.')
                % task.id)

        self._tasks[task.id] = task

    def evolve(self):
        """Perform the evolution.

        This will run through all queued tasks and attempt to apply them in
        a database transaction, tracking each new batch of evolutions as the
        tasks finish.

        This can only be called once per evolver instance.

        Raises:
            django_evolution.errors.EvolutionException:
                Something went wrong during the evolution process. Details
                are in the error message. Note that a more specific exception
                may be raised.

            django_evolution.errors.EvolutionExecutionError:
                A specific evolution task failed. Details are in the error.
        """
        if self.evolved:
            raise EvolutionException(
                _('Evolver.evolve() has already been run once. It cannot be '
                  'run again.'))

        self._prepare_tasks()

        connection = connections[self.database_name]

        with connection.constraint_checks_disabled():
            with transaction.atomic(using=self.database_name):
                cursor = connection.cursor()
                new_evolutions = []

                try:
                    for task in self.tasks:
                        # Perform the evolution for the app. This is
                        # responsible for raising any exceptions.
                        task.execute(cursor)
                        new_evolutions += task.new_evolutions
                finally:
                    cursor.close()

                try:
                    # Now save the current signature and version.
                    version = Version.objects.create(
                        signature=self.project_sig)

                    for evolution in new_evolutions:
                        evolution.version = version

                    Evolution.objects.bulk_create(new_evolutions)
                except Exception as e:
                    raise EvolutionExecutionError(
                        _('Error saving new evolution version information: %s')
                        % e,
                        detailed_error=six.text_type(e))

        self.evolved = True

    def _prepare_tasks(self):
        """Prepare all queued tasks for further operations.

        Once prepared, no new tasks can be added. This will be done before
        performing any operations requiring state from queued tasks.
        """
        if not self._tasks_prepared:
            self._tasks_prepared = True

            for task in self.tasks:
                task.prepare(hinted=self.hinted)


def get_evolution_sequence(app):
    """Return the list of evolution labels for a Django app.

    Args:
        app (module):
            The app to return evolutions for.

    Returns:
        list of unicode:
        The list of evolution labels.
    """
    app_name = get_app_name(app)

    if app_name in BUILTIN_SEQUENCES:
        return BUILTIN_SEQUENCES[app_name]

    try:
        return import_module('%s.evolutions' % app_name).SEQUENCE
    except Exception:
        return []


def get_unapplied_evolutions(app, database=DEFAULT_DB_ALIAS):
    """Return the list of labels for unapplied evolutions for a Django app.

    Args:
        app (module):
            The app to return evolutions for.

        database (unicode, optional):
            The name of the database containing the
            :py:class:`~django_evolution.models.Evolution` entries.

    Returns:
        list of unicode:
        The labels of evolutions that have not yet been applied.
    """
    applied = set(
        Evolution.objects
        .using(database)
        .filter(app_label=get_app_label(app))
        .values_list('label', flat=True)
    )

    return [
        evolution_name
        for evolution_name in get_evolution_sequence(app)
        if evolution_name not in applied
    ]


def get_mutations(app, evolution_labels, database=DEFAULT_DB_ALIAS):
    """Return the mutations provided by the given evolution names.

    Args:
        app (module):
            The app the evolutions belong to.

        evolution_labels (unicode):
            The labels of the evolutions to return mutations for.

        database (unicode, optional):
            The name of the database the evolutions cover.

    Returns:
        list of django_evolution.mutations.BaseMutation:
        The list of mutations provided by the evolutions.

    Raises:
        django_evolution.errors.EvolutionException:
            One or more evolutions are missing.
    """
    # For each item in the evolution sequence. Check each item to see if it is
    # a python file or an sql file.
    try:
        app_name = get_app_name(app)

        if app_name in BUILTIN_SEQUENCES:
            module_name = 'django_evolution.builtin_evolutions'
        else:
            module_name = '%s.evolutions' % app_name

        evolution_module = import_module(module_name)
    except ImportError:
        return []

    mutations = []

    for label in evolution_labels:
        directory_name = os.path.dirname(evolution_module.__file__)

        # The first element is used for compatibility purposes.
        filenames = [
            os.path.join(directory_name, label + '.sql'),
            os.path.join(directory_name, "%s_%s.sql" % (database, label)),
        ]

        found = False

        for filename in filenames:
            if os.path.exists(filename):
                sql_file = open(filename, 'r')
                sql = sql_file.readlines()
                sql_file.close()

                mutations.append(SQLMutation(label, sql))

                found = True
                break

        if not found:
            try:
                module_name = [evolution_module.__name__, label]
                module = __import__('.'.join(module_name),
                                    {}, {}, [module_name])
                mutations.extend(module.MUTATIONS)
            except ImportError:
                raise EvolutionException(
                    'Error: Failed to find an SQL or Python evolution named %s'
                    % label)

    latest_version = Version.objects.current_version(using=database)

    app_id = get_app_label(app)
    old_project_sig = latest_version.signature
    project_sig = ProjectSignature.from_database(database)

    old_app_sig = old_project_sig.get_app_sig(app_id)
    app_sig = project_sig.get_app_sig(app_id)

    if old_app_sig is not None and app_sig is not None:
        # We want to go through now and make sure we're only applying
        # evolutions for models where the signature is different between
        # what's stored and what's current.
        #
        # The reason for this is that we may have just installed a baseline,
        # which would have the up-to-date signature, and we might be trying
        # to apply evolutions on top of that (which would already be applied).
        # These would generate errors. So, try hard to prevent that.
        #
        # First, Find the list of models in the latest signature of this app
        # that aren't in the old signature.
        changed_models = set(
            model_sig.model_name
            for model_sig in app_sig.model_sigs
            if old_app_sig.get_model_sig(model_sig.model_name) != model_sig
        )

        # Now do the same for models in the old signature, in case the
        # model has been deleted.
        changed_models.update(
            old_model_sig.model_name
            for old_model_sig in old_app_sig.model_sigs
            if app_sig.get_model_sig(old_model_sig.model_name) is None
        )

        # We should now have a full list of which models changed. Filter
        # the list of mutations appropriately.
        #
        # Changes affecting a model that was newly-introduced are removed,
        # unless the mutation is a RenameModel, in which case we'll need it
        # during the optimization step (and will remove it if necessary then).
        mutations = [
            mutation
            for mutation in mutations
            if (not hasattr(mutation, 'model_name') or
                mutation.model_name in changed_models or
                isinstance(mutation, RenameModel))
        ]

    return mutations
