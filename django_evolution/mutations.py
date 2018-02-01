"""Support for schema mutation operations and hint output."""

from __future__ import unicode_literals

import copy

from django.db import models
from django.utils import six
from django.utils.functional import curry

from django_evolution.db import EvolutionOperationsMulti
from django_evolution.db.sql_result import SQLResult
from django_evolution.errors import (CannotSimulate, SimulationFailure,
                                     EvolutionNotImplementedError)
from django_evolution.mock_models import MockModel, MockRelated, create_field
from django_evolution.signature import (ATTRIBUTE_DEFAULTS,
                                        record_unique_together_applied)
from django_evolution.utils import get_database_for_model_name


class BaseMutation(object):
    """Base class for a schema mutation.

    These are responsible for simulating schema mutations and applying actual
    mutations to a database signature.
    """

    def generate_hint(self):
        """Return a hinted evolution for the mutation.

        This will generate a line that will be used in a hinted evolution
        file. This method generally should not be overridden. Instead, use
        :py:meth:`get_hint_params`.

        Returns:
            unicode:
            A hinted evolution statement for this mutation.
        """
        return '%s(%s)' % (self.__class__.__name__,
                           ', '.join(self.get_hint_params()))

    def get_hint_params(self):
        """Return parameters for the mutation's hinted evolution.

        Returns:
            list of unicode:
            A list of parameter strings to pass to the mutation's constructor
            in a hinted evolution.
        """
        return []

    def simulate(self, app_label, proj_sig, database_sig, database=None):
        """Simulate a mutation for an application.

        This will attempt to perform a mutation on the database signature,
        modifying it to match the state described to the mutation. This allows
        Django Evolution to test evolutions before they hit the database.

        Args:
            app_label (unicode):
                The label for the Django application being mutated.

            proj_sig (dict):
                The project's schema signature.

            database_sig (dict):
                The database's schema signature.

            database (unicode, optional):
                The name of the database the operation is being performed on.

        Raises:
            django_evolution.errors.CannotSimulate:
                The simulation cannot be executed for this mutation. The
                reason is in the exception's message.

            django_evolution.errors.SimulationFailure:
                The simulation failed. The reason is in the exception's
                message.
        """
        raise NotImplementedError

    def mutate(self, mutator):
        """Schedule a database mutation on the mutator.

        This will instruct the mutator to perform one or more database
        mutations for an app. Those will be scheduled and later executed on the
        database, if not optimized out.

        Args:
            mutator (django_evolution.mutators.AppMutator):
                The mutator to perform an operation on.

        Raises:
            django_evolution.errors.EvolutionNotImplementedError:
                The configured mutation is not supported on this type of
                database.
        """
        raise NotImplementedError

    def is_mutable(self, app_label, proj_sig, database_sig, database):
        """Return whether the mutation can be applied to the database.

        This should check if the database or parts of the signature matches
        the attributes provided to the mutation.

        Args:
            app_label (unicode):
                The label for the Django application to be mutated.

            proj_sig (dict):
                The project's schema signature.

            database_sig (dict):
                The database's schema signature.

            database (unicode):
                The name of the database the operation would be performed on.

        Returns:
            bool:
            ``True`` if the mutation can run. ``False`` if it cannot.
        """
        return False

    def serialize_value(self, value):
        """Serialize a value for use in a mutation statement.

        This will attempt to represent the value as something Python can
        execute, across Python versions. The string representation of the
        value is used by default. If that representation is of a Unicode
        string, and that string include a ``u`` prefix, it will be stripped.

        Args:
            value (object):
                The value to serialize.

        Returns:
            unicode:
            The serialized string.
        """
        if isinstance(value, six.string_types):
            value = six.text_type(value)

        value_repr = repr(value)

        if isinstance(value, six.text_type) and value_repr.startswith('u'):
            value_repr = value_repr[1:]

        return value_repr

    def serialize_attr(self, attr_name, attr_value):
        """Serialize an attribute for use in a mutation statement.

        This will create a ``name=value`` string, with the value serialized
        using :py:meth:`serialize_value`.

        Args:
            attr_name (unicode):
                The attribute's name.

            attr_value (object):
                The attribute's value.

        Returns:
            unicode:
            The serialized attribute string.
        """
        return '%s=%s' % (attr_name, self.serialize_value(attr_value))

    def __str__(self):
        """Return a hinted evolution for the mutation.

        Returns:
            unicode:
            The hinted evolution.
        """
        return self.generate_hint()

    def __repr__(self):
        """Return a string representation of the mutation.

        Returns:
            unicode:
            A string representation of the mutation.
        """
        return '<%s>' % self


class MonoBaseMutation(BaseMutation):
    """Base class for a mutation affecting a single model."""

    def __init__(self, model_name):
        """Initialize the mutation.

        Args:
            model_name (unicode):
                The name of the model being mutated.
        """
        super(MonoBaseMutation, self).__init__()
        self.model_name = model_name

    def evolver(self, model, database_sig, database=None):
        if database is None:
            database = get_database_for_model_name(model.app_label,
                                                   model.model_name)

        return EvolutionOperationsMulti(database, database_sig).get_evolver()

    def is_mutable(self, app_label, proj_sig, database_sig, database):
        """Return whether the mutation can be applied to the database.

        This will if the database matches that of the model.

        Args:
            app_label (unicode):
                The label for the Django application to be mutated.

            proj_sig (dict, unused):
                The project's schema signature.

            database_sig (dict, unused):
                The database's schema signature.

            database (unicode):
                The name of the database the operation would be performed on.

        Returns:
            bool:
            ``True`` if the mutation can run. ``False`` if it cannot.
        """
        db_name = (database or
                   get_database_for_model_name(app_label, self.model_name))
        return db_name and db_name == database


class SQLMutation(BaseMutation):
    """A mutation that executes SQL on the database.

    Unlike most mutations, this one is largely database-dependent. It allows
    arbitrary SQL to be executed. It's recommended that the execution does
    not modify the schema of a table (unless it's highly database-specific with
    no counterpart in Django Evolution), but rather is limited to things like
    populating data.

    SQL statements cannot be optimized. Any scheduled database operations
    prior to the SQL statement will be executed without any further
    optimization. This can lead to longer database evolution times.
    """

    def __init__(self, tag, sql, update_func=None):
        """Initialize the mutation.

        Args:
            tag (unicode):
                A unique tag identifying this SQL operation.

            sql (unicode):
                The SQL to execute.

            update_func (callable, optional):
                A function to call to simulate updating the database signature.
                This is required for :py:meth:`simulate` to work.
        """
        self.tag = tag
        self.sql = sql
        self.update_func = update_func

    def get_hint_params(self):
        """Return parameters for the mutation's hinted evolution.

        Returns:
            list of unicode:
            A list of parameter strings to pass to the mutation's constructor
            in a hinted evolution.
        """
        return [self.tag]

    def simulate(self, app_label, proj_sig, database_sig, database=None):
        """Simulate a mutation for an application.

        This will run the :py:attr:`update_func` provided when instantiating
        the mutation, passing it ``app_label`` and ``proj_sig``. It should
        then modify the signature to match what the SQL statement would do.

        Args:
            app_label (unicode):
                The label for the Django application being mutated.

            proj_sig (dict):
                The project's schema signature.

            database_sig (dict):
                The database's schema signature.

            database (unicode, optional):
                The name of the database the operation is being performed on.

        Raises:
            django_evolution.errors.CannotSimulate:
                :py:attr:`update_func` was not provided or was not a function.

            django_evolution.errors.SimulationFailure:
                The simulation failed. The reason is in the exception's
                message. This would be run by :py:attr:`update_func`.
        """
        if callable(self.update_func):
            self.update_func(app_label, proj_sig)
        else:
            raise CannotSimulate('Cannot simulate SQLMutations')

    def mutate(self, mutator):
        """Schedule a database mutation on the mutator.

        This will instruct the mutator to execute the SQL for an app.

        Args:
            mutator (django_evolution.mutators.AppMutator):
                The mutator to perform an operation on.

        Raises:
            django_evolution.errors.EvolutionNotImplementedError:
                The configured mutation is not supported on this type of
                database.
        """
        mutator.add_sql(self, self.sql)

    def is_mutable(self, *args, **kwargs):
        """Return whether the mutation can be applied to the database.

        Args:
            *args (tuple, unused):
                Unused positional arguments.

            **kwargs (tuple, unused):
                Unused positional arguments.

        Returns:
            bool:
            ``True``, always.
        """
        return True


class MutateModelField(MonoBaseMutation):
    """Base class for any fields that mutate a model.

    This is used for classes that perform any mutation on a model. Such
    mutations will be provided a model they can work with.

    Operations added to the mutator by this field will be associated with that
    model. That will allow the operations backend to perform any optimizations
    to improve evolution time for the model.
    """

    def mutate(self, mutator, model):
        """Schedule a model mutation on the mutator.

        This will instruct the mutator to perform one or more database
        mutations for a model. Those will be scheduled and later executed on
        the database, if not optimized out.

        Args:
            mutator (django_evolution.mutators.ModelMutator):
                The mutator to perform an operation on.

            model (MockModel):
                The model being mutated.

        Raises:
            django_evolution.errors.EvolutionNotImplementedError:
                The configured mutation is not supported on this type of
                database.
        """
        raise NotImplementedError


class DeleteField(MutateModelField):
    """A mutation that deletes a field from a model."""

    def __init__(self, model_name, field_name):
        """Initialize the mutation.

        Args:
            model_name (unicode):
                The name of the model containing the field.

            field_name (unicode):
                The name of the field to delete.
        """
        super(DeleteField, self).__init__(model_name)
        self.field_name = field_name

    def get_hint_params(self):
        """Return parameters for the mutation's hinted evolution.

        Returns:
            list of unicode:
            A list of parameter strings to pass to the mutation's constructor
            in a hinted evolution.
        """
        return [
            self.serialize_value(self.model_name),
            self.serialize_value(self.field_name),
        ]

    def simulate(self, app_label, proj_sig, database_sig, database=None):
        """Simulate the mutation.

        This will alter the database schema to remove the specified field,
        modifying meta fields (``unique_together``) if necessary.

        It will also check to make sure this is not a primary key and that
        the field exists.

        Args:
            app_label (unicode):
                The label for the Django application being mutated.

            proj_sig (dict):
                The project's schema signature.

            database_sig (dict):
                The database's schema signature.

            database (unicode, optional):
                The name of the database the operation is being performed on.

        Raises:
            django_evolution.errors.SimulationFailure:
                The simulation failed. The reason is in the exception's
                message.
        """
        try:
            app_sig = proj_sig[app_label]
        except KeyError:
            raise SimulationFailure(
                'Cannot delete the field "%s" on model "%s.%s". The '
                'application could not be found in the signature.'
                % (self.field_name, app_label, self.model_name))

        try:
            model_sig = app_sig[self.model_name]
        except KeyError:
            raise SimulationFailure(
                'Cannot delete the field "%s" on model "%s.%s". The model '
                'could not be found in the signature.'
                % (self.field_name, app_label, self.model_name))

        try:
            fields_sig = model_sig['fields']
            field = fields_sig[self.field_name]
        except KeyError:
            raise SimulationFailure(
                'Cannot delete the field "%s" on model "%s.%s". The field '
                'could not be found in the signature.'
                % (self.field_name, app_label, self.model_name))

        if field.get('primary_key', False):
            raise SimulationFailure(
                'The field "%s" on model "%s.%s" is the primary key, and '
                'cannot be deleted.'
                % (self.field_name, app_label, self.model_name))

        # If the field was used in the unique_together attribute, update it.
        unique_together = model_sig['meta']['unique_together']
        unique_together_list = []

        for ut_index in range(0, len(unique_together), 1):
            ut = unique_together[ut_index]
            unique_together_fields = []

            for field_name_index in range(0, len(ut), 1):
                field_name = ut[field_name_index]

                if not field_name == self.field_name:
                    unique_together_fields.append(field_name)

            unique_together_list.append(tuple(unique_together_fields))

        model_sig['meta']['unique_together'] = tuple(unique_together_list)

        # Simulate the deletion of the field.
        del fields_sig[self.field_name]

    def mutate(self, mutator, model):
        """Schedule a field deletion on the mutator.

        This will instruct the mutator to perform a deletion of a field on
        a model. It will be scheduled and later executed on the database, if
        not optimized out.

        Args:
            mutator (django_evolution.mutators.ModelMutator):
                The mutator to perform an operation on.

            model (MockModel):
                The model being mutated.
        """
        field_sig = mutator.model_sig['fields'][self.field_name]

        # Temporarily remove field_type from the field signature
        # so that we can create a field
        field_type = field_sig.pop('field_type')
        field = create_field(mutator.proj_sig, self.field_name, field_type,
                             field_sig, model)
        field_sig['field_type'] = field_type

        if field_type is models.ManyToManyField:
            mutator.add_sql(
                self,
                mutator.evolver.delete_table(
                    field._get_m2m_db_table(model._meta)))
        else:
            mutator.delete_column(self, field)


class AddField(MutateModelField):
    """A mutation that adds a field to a model."""

    def __init__(self, model_name, field_name, field_type, initial=None,
                 **field_attrs):
        """Initialize the mutation.

        Args:
            model_name (unicode):
                The name of the model to add the field to.

            field_name (unicode):
                The name of the new field.

            field_type (cls):
                The field class to use. This must be a subclass of
                :py:class:`django.db.models.Field`.

            initial (object, optional):
                The initial value for the field. This is required if non-null.

            **field_attrs (dict):
                Attributes to set on the field.
        """
        super(AddField, self).__init__(model_name)
        self.field_name = field_name
        self.field_type = field_type
        self.field_attrs = field_attrs
        self.initial = initial

    def get_hint_params(self):
        """Return parameters for the mutation's hinted evolution.

        Returns:
            list of unicode:
            A list of parameter strings to pass to the mutation's constructor
            in a hinted evolution.
        """
        if self.field_type.__module__.startswith('django.db.models'):
            field_prefix = 'models.'
        else:
            field_prefix = ''

        params = [
            self.serialize_value(self.model_name),
            self.serialize_value(self.field_name),
            field_prefix + self.field_type.__name__,
        ]

        if self.initial is not None:
            params.append(self.serialize_attr('initial', self.initial))

        params += [
            self.serialize_attr(key, value)
            for key, value in six.iteritems(self.field_attrs)
        ]

        return params

    def simulate(self, app_label, proj_sig, database_sig, database=None):
        """Simulate the mutation.

        This will alter the database schema to add the specified field.

        Args:
            app_label (unicode):
                The label for the Django application being mutated.

            proj_sig (dict):
                The project's schema signature.

            database_sig (dict):
                The database's schema signature.

            database (unicode, optional):
                The name of the database the operation is being performed on.

        Raises:
            django_evolution.errors.SimulationFailure:
                The simulation failed. The reason is in the exception's
                message.
        """
        try:
            app_sig = proj_sig[app_label]
        except KeyError:
            raise SimulationFailure(
                'Cannot add the field "%s" to model "%s.%s". The application '
                'could not be found in the signature.'
                % (self.field_name, app_label, self.model_name))

        try:
            model_sig = app_sig[self.model_name]
        except KeyError:
            raise SimulationFailure(
                'Cannot add the field "%s" to model "%s.%s". The model could '
                'not be found in the signature.'
                % (self.field_name, app_label, self.model_name))

        if self.field_name in model_sig['fields']:
            raise SimulationFailure(
                'The model "%s.%s" already has a field named "%s".'
                % (app_label, self.model_name, self.field_name))

        if (self.field_type is not models.ManyToManyField and
            not self.field_attrs.get('null', ATTRIBUTE_DEFAULTS['null'])
            and self.initial is None):
            raise SimulationFailure(
                'Cannot create new field "%s" on model "%s.%s". A non-null '
                'initial value must be specified in the mutation.'
                % (self.field_name, app_label, self.model_name))

        model_sig['fields'][self.field_name] = {
            'field_type': self.field_type,
        }

        model_sig['fields'][self.field_name].update(self.field_attrs)

    def mutate(self, mutator, model):
        """Schedule a field addition on the mutator.

        This will instruct the mutator to add a new field on a model. It will
        be scheduled and later executed on the database, if not optimized out.

        Args:
            mutator (django_evolution.mutators.ModelMutator):
                The mutator to perform an operation on.

            model (MockModel):
                The model being mutated.
        """
        if self.field_type is models.ManyToManyField:
            self.add_m2m_table(mutator, model)
        else:
            self.add_column(mutator, model)

    def add_column(self, mutator, model):
        """Add a standard column to the model.

        Args:
            mutator (django_evolution.mutators.ModelMutator):
                The mutator to perform an operation on.

            model (MockModel):
                The model being mutated.
        """
        field = create_field(mutator.proj_sig, self.field_name,
                             self.field_type, self.field_attrs, model)

        mutator.add_column(self, field, self.initial)

    def add_m2m_table(self, mutator, model):
        """Add a ManyToMany column to the model and an accompanying table.

        Args:
            mutator (django_evolution.mutators.ModelMutator):
                The mutator to perform an operation on.

            model (MockModel):
                The model being mutated.
        """
        field = create_field(mutator.proj_sig, self.field_name,
                             self.field_type, self.field_attrs, model)

        related_app_label, related_model_name = \
            self.field_attrs['related_model'].split('.')
        related_sig = mutator.proj_sig[related_app_label][related_model_name]
        related_model = MockModel(mutator.proj_sig, related_app_label,
                                  related_model_name, related_sig,
                                  mutator.database)
        related = MockRelated(related_model, model, field)

        if hasattr(field, '_get_m2m_column_name'):
            # Django < 1.2
            field.m2m_column_name = \
                curry(field._get_m2m_column_name, related)
            field.m2m_reverse_name = \
                curry(field._get_m2m_reverse_name, related)
        else:
            # Django >= 1.2
            field.m2m_column_name = curry(field._get_m2m_attr,
                                          related, 'column')
            field.m2m_reverse_name = curry(field._get_m2m_reverse_attr,
                                           related, 'column')

        mutator.add_sql(self, mutator.evolver.add_m2m_table(model, field))


class RenameField(MutateModelField):
    """A mutation that renames a field on a model."""

    def __init__(self, model_name, old_field_name, new_field_name,
                 db_column=None, db_table=None):
        """Initialize the mutation.

        Args:
            model_name (unicode):
                The name of the model to add the field to.

            old_field_name (unicode):
                The old (existing) name of the field.

            new_field_name (unicode):
                The new name for the field.

            db_column (unicode, optional):
                The explicit column name to set for the field.

            db_table (object, optional):
                The explicit table name to use, if specifying a
                :py:class:`~django.db.models.ManyToManyField`.
        """
        super(RenameField, self).__init__(model_name)
        self.old_field_name = old_field_name
        self.new_field_name = new_field_name
        self.db_column = db_column
        self.db_table = db_table

    def get_hint_params(self):
        """Return parameters for the mutation's hinted evolution.

        Returns:
            list of unicode:
            A list of parameter strings to pass to the mutation's constructor
            in a hinted evolution.
        """
        params = [
            self.serialize_value(self.model_name),
            self.serialize_value(self.old_field_name),
            self.serialize_value(self.new_field_name),
        ]

        if self.db_column:
            params.append(self.serialize_attr('db_column', self.db_column))

        if self.db_table:
            params.append(self.serialize_attr('db_table', self.db_table))

        return params

    def simulate(self, app_label, proj_sig, database_sig, database=None):
        """Simulate the mutation.

        This will alter the database schema to rename the specified field.

        Args:
            app_label (unicode):
                The label for the Django application being mutated.

            proj_sig (dict):
                The project's schema signature.

            database_sig (dict):
                The database's schema signature.

            database (unicode, optional):
                The name of the database the operation is being performed on.

        Raises:
            django_evolution.errors.SimulationFailure:
                The simulation failed. The reason is in the exception's
                message.
        """
        try:
            app_sig = proj_sig[app_label]
        except KeyError:
            raise SimulationFailure(
                'Cannot rename the field "%s" on model "%s.%s". The '
                'application could not be found in the signature.'
                % (self.old_field_name, app_label, self.model_name))

        try:
            model_sig = app_sig[self.model_name]
        except KeyError:
            raise SimulationFailure(
                'Cannot rename the field "%s" on model "%s.%s". The model '
                'could not be found in the signature.'
                % (self.old_field_name, app_label, self.model_name))

        try:
            field_dict = model_sig['fields']
            field_sig = field_dict[self.old_field_name]
        except KeyError:
            raise SimulationFailure(
                'Cannot rename the field "%s" on model "%s.%s". The field '
                'could not be found in the signature.'
                % (self.old_field_name, app_label, self.model_name))

        if models.ManyToManyField == field_sig['field_type']:
            if self.db_table:
                field_sig['db_table'] = self.db_table
            else:
                field_sig.pop('db_table', None)
        elif self.db_column:
            field_sig['db_column'] = self.db_column
        else:
            # db_column and db_table were not specified (or not specified for
            # the appropriate field types). Clear the old value if one was set.
            # This amounts to resetting the column or table name to the Django
            # default name
            field_sig.pop('db_column', None)

        field_dict[self.new_field_name] = field_dict.pop(self.old_field_name)

    def mutate(self, mutator, model):
        """Schedule a field rename on the mutator.

        This will instruct the mutator to rename a field on a model. It will be
        scheduled and later executed on the database, if not optimized out.

        Args:
            mutator (django_evolution.mutators.ModelMutator):
                The mutator to perform an operation on.

            model (MockModel):
                The model being mutated.
        """
        old_field_sig = mutator.model_sig['fields'][self.old_field_name]

        # Temporarily remove the field type so that we can create mock field
        # instances.
        field_type = old_field_sig.pop('field_type')

        # Duplicate the old field sig, and apply the table/column changes.
        new_field_sig = copy.copy(old_field_sig)

        if field_type is models.ManyToManyField:
            if self.db_table:
                new_field_sig['db_table'] = self.db_table
            else:
                new_field_sig.pop('db_table', None)
        elif self.db_column:
            new_field_sig['db_column'] = self.db_column
        else:
            new_field_sig.pop('db_column', None)

        # Create the mock field instances.
        old_field = create_field(mutator.proj_sig, self.old_field_name,
                                 field_type, old_field_sig, None)
        new_field = create_field(mutator.proj_sig, self.new_field_name,
                                 field_type, new_field_sig, None)

        # Restore the field type to the signature
        old_field_sig['field_type'] = field_type

        new_model = MockModel(mutator.proj_sig, mutator.app_label,
                              self.model_name, mutator.model_sig,
                              db_name=mutator.database)
        evolver = mutator.evolver

        if field_type is models.ManyToManyField:
            old_m2m_table = old_field._get_m2m_db_table(new_model._meta)
            new_m2m_table = new_field._get_m2m_db_table(new_model._meta)

            sql = evolver.rename_table(new_model, old_m2m_table, new_m2m_table)
        else:
            sql = evolver.rename_column(new_model, old_field, new_field)

        mutator.add_sql(self, sql)


class ChangeField(MutateModelField):
    """A mutation that changes attributes on a field on a model."""

    def __init__(self, model_name, field_name, initial=None, **field_attrs):
        """Initialize the mutation.

        Args:
            model_name (unicode):
                The name of the model containing the field to change.

            field_name (unicode):
                The name of the field to change.

            initial (object, optional):
                The initial value for the field. This is required if non-null.

            **field_attrs (dict):
                Attributes to set on the field.
        """
        super(ChangeField, self).__init__(model_name)
        self.field_name = field_name
        self.field_attrs = field_attrs
        self.initial = initial

    def get_hint_params(self):
        """Return parameters for the mutation's hinted evolution.

        Returns:
            list of unicode:
            A list of parameter strings to pass to the mutation's constructor
            in a hinted evolution.
        """
        return [
            self.serialize_value(self.model_name),
            self.serialize_value(self.field_name),
            self.serialize_attr('initial', self.initial),
        ] + [
            self.serialize_attr(attr_name, attr_value)
            for attr_name, attr_value in six.iteritems(self.field_attrs)
        ]

    def simulate(self, app_label, proj_sig, database_sig, database=None):
        """Simulate the mutation.

        This will alter the database schema to change attributes for the
        specified field.

        Args:
            app_label (unicode):
                The label for the Django application being mutated.

            proj_sig (dict):
                The project's schema signature.

            database_sig (dict):
                The database's schema signature.

            database (unicode, optional):
                The name of the database the operation is being performed on.

        Raises:
            django_evolution.errors.SimulationFailure:
                The simulation failed. The reason is in the exception's
                message.
        """
        try:
            app_sig = proj_sig[app_label]
        except KeyError:
            raise SimulationFailure(
                'Cannot change the field "%s" on model "%s.%s". The '
                'application could not be found in the signature.'
                % (self.field_name, app_label, self.model_name))

        try:
            model_sig = app_sig[self.model_name]
        except KeyError:
            raise SimulationFailure(
                'Cannot change the field "%s" on model "%s.%s". The model '
                'could not be found in the signature.'
                % (self.field_name, app_label, self.model_name))

        try:
            field_sig = model_sig['fields'][self.field_name]
        except KeyError:
            raise SimulationFailure(
                'Cannot change the field "%s" on model "%s.%s". The field '
                'could not be found in the signature.'
                % (self.field_name, app_label, self.model_name))

        # Catch for no-op changes.
        for field_attr, attr_value in self.field_attrs.items():
            field_sig[field_attr] = attr_value

        if ('null' in self.field_attrs and
            field_sig['field_type'] != models.ManyToManyField and
            not self.field_attrs['null'] and
            self.initial is None):
            raise SimulationFailure(
                'Cannot change the field "%s" on model "%s.%s". A non-null '
                'initial value needs to be specified in the mutation.'
                % (self.field_name, app_label, self.model_name))

    def mutate(self, mutator, model):
        """Schedule a field change on the mutator.

        This will instruct the mutator to change attributes on a field on a
        model. It will be scheduled and later executed on the database, if not
        optimized out.

        Args:
            mutator (django_evolution.mutators.ModelMutator):
                The mutator to perform an operation on.

            model (MockModel):
                The model being mutated.
        """
        field_sig = mutator.model_sig['fields'][self.field_name]
        field = model._meta.get_field(self.field_name)

        for attr_name in six.iterkeys(self.field_attrs):
            if attr_name not in mutator.evolver.supported_change_attrs:
                raise EvolutionNotImplementedError(
                    "ChangeField does not support modifying the '%s' "
                    "attribute on '%s.%s'."
                    % (attr_name, self.model_name, self.field_name))

        new_field_attrs = {}

        for attr_name, attr_value in six.iteritems(self.field_attrs):
            old_attr_value = field_sig.get(attr_name,
                                           ATTRIBUTE_DEFAULTS[attr_name])

            # Avoid useless SQL commands if nothing has changed.
            if old_attr_value != attr_value:
                new_field_attrs[attr_name] = {
                    'old_value': old_attr_value,
                    'new_value': attr_value,
                }

        if new_field_attrs:
            mutator.change_column(self, field, new_field_attrs)


class RenameModel(MutateModelField):
    """A mutation that renames a model."""

    def __init__(self, old_model_name, new_model_name, db_table):
        """Initialize the mutation.

        Args:
            old_model_name (unicode):
                The old (existing) name of the model to rename.

            new_model_name (unicode):
                The new name for the model.

            db_table (unicode):
                The table name in the database for this model.
        """
        super(RenameModel, self).__init__(old_model_name)
        self.old_model_name = old_model_name
        self.new_model_name = new_model_name
        self.db_table = db_table

    def get_hint_params(self):
        """Return parameters for the mutation's hinted evolution.

        Returns:
            list of unicode:
            A list of parameter strings to pass to the mutation's constructor
            in a hinted evolution.
        """
        params = [
            self.serialize_value(self.old_model_name),
            self.serialize_value(self.new_model_name),
        ]

        if self.db_table:
            params.append(self.serialize_attr('db_table', self.db_table)),

        return params

    def simulate(self, app_label, proj_sig, database_sig, database=None):
        """Simulate the mutation.

        This will alter the database schema to rename the specified model.

        Args:
            app_label (unicode):
                The label for the Django application being mutated.

            proj_sig (dict):
                The project's schema signature.

            database_sig (dict):
                The database's schema signature.

            database (unicode, optional):
                The name of the database the operation is being performed on.

        Raises:
            django_evolution.errors.SimulationFailure:
                The simulation failed. The reason is in the exception's
                message.
        """
        try:
            app_sig = proj_sig[app_label]
        except KeyError:
            raise SimulationFailure(
                'Cannot rename the model "%s.%s". The application could '
                'not be found in the signature.'
                % (app_label, self.old_model_name))

        try:
            model_sig = app_sig[self.old_model_name]
        except KeyError:
            raise SimulationFailure(
                'Cannot rename the model "%s.%s". The model could not be '
                'found in the signature.'
                % (app_label, self.old_model_name))

        if self.db_table:
            model_sig['meta']['db_table'] = self.db_table
        else:
            # db_table was not specified. Clear the old value if one was set.
            # This amounts to resetting the column or table name to the Django
            # default name.
            model_sig['meta'].pop('db_table', None)

        app_sig[self.new_model_name] = app_sig.pop(self.old_model_name)

        old_related_model = '%s.%s' % (app_label, self.old_model_name)
        new_related_model = '%s.%s' % (app_label, self.new_model_name)

        for app_sig in six.itervalues(proj_sig):
            if not isinstance(app_sig, dict):
                continue

            for model_sig in six.itervalues(app_sig):
                for field in six.itervalues(model_sig['fields']):
                    if ('related_model' in field and
                        field['related_model'] == old_related_model):
                        field['related_model'] = new_related_model

    def mutate(self, mutator, model):
        """Schedule a model rename on the mutator.

        This will instruct the mutator to rename a model. It will be scheduled
        and later executed on the database, if not optimized out.

        Args:
            mutator (django_evolution.mutators.ModelMutator):
                The mutator to perform an operation on.

            model (MockModel):
                The model being mutated.
        """
        old_model_sig = mutator.model_sig
        new_model_sig = copy.deepcopy(old_model_sig)

        new_model_sig['meta']['db_table'] = self.db_table

        new_model = MockModel(mutator.proj_sig, mutator.app_label,
                              self.new_model_name, new_model_sig,
                              db_name=mutator.database)
        evolver = mutator.evolver

        sql = evolver.rename_table(new_model,
                                   old_model_sig['meta']['db_table'],
                                   new_model_sig['meta']['db_table'])

        mutator.add_sql(self, sql)


class DeleteModel(MutateModelField):
    """A mutation that deletes a model."""

    def get_hint_params(self):
        """Return parameters for the mutation's hinted evolution.

        Returns:
            list of unicode:
            A list of parameter strings to pass to the mutation's constructor
            in a hinted evolution.
        """
        return [self.serialize_value(self.model_name)]

    def simulate(self, app_label, proj_sig, database_sig, database=None):
        """Simulate the mutation.

        This will alter the database schema to delete the specified model.

        Args:
            app_label (unicode):
                The label for the Django application being mutated.

            proj_sig (dict):
                The project's schema signature.

            database_sig (dict):
                The database's schema signature.

            database (unicode, optional):
                The name of the database the operation is being performed on.

        Raises:
            django_evolution.errors.SimulationFailure:
                The simulation failed. The reason is in the exception's
                message.
        """
        try:
            app_sig = proj_sig[app_label]
        except KeyError:
            raise SimulationFailure(
                'Cannot delete the model "%s.%s". The application could '
                'not be found in the signature.'
                % (app_label, self.model_name))

        # Simulate the deletion of the model.
        try:
            del app_sig[self.model_name]
        except KeyError:
            raise SimulationFailure(
                'Cannot delete the model "%s.%s". The model could not be '
                'found in the signature.'
                % (app_label, self.model_name))

    def mutate(self, mutator, model):
        """Schedule a model deletion on the mutator.

        This will instruct the mutator to delete a model. It will be scheduled
        and later executed on the database, if not optimized out.

        Args:
            mutator (django_evolution.mutators.ModelMutator):
                The mutator to perform an operation on.

            model (MockModel):
                The model being mutated.
        """
        sql_result = SQLResult()

        # Remove any many to many tables.
        for field_name, field_sig in mutator.model_sig['fields'].items():
            if field_sig['field_type'] is models.ManyToManyField:
                field = model._meta.get_field(field_name)
                m2m_table = field._get_m2m_db_table(model._meta)
                sql_result.add(mutator.evolver.delete_table(m2m_table))

        # Remove the table itself.
        sql_result.add(mutator.evolver.delete_table(model._meta.db_table))

        mutator.add_sql(self, sql_result)


class DeleteApplication(BaseMutation):
    """A mutation that deletes an application."""

    def simulate(self, app_label, proj_sig, database_sig, database=None):
        """Simulate the mutation.

        This will alter the database schema to delete the specified
        application.

        Args:
            app_label (unicode):
                The label for the Django application being mutated.

            proj_sig (dict):
                The project's schema signature.

            database_sig (dict):
                The database's schema signature.

            database (unicode, optional):
                The name of the database the operation is being performed on.

        Raises:
            django_evolution.errors.SimulationFailure:
                The simulation failed. The reason is in the exception's
                message.
        """
        if not database:
            return

        try:
            app_sig = proj_sig[app_label]
        except KeyError:
            raise SimulationFailure(
                'Cannot delete the application "%s". It could not be found '
                'in the signature.'
                % app_label)

        # Simulate the deletion of the models.
        for model_name in app_sig.keys():
            mutation = DeleteModel(model_name)

            if mutation.is_mutable(app_label, proj_sig, database_sig,
                                   database):
                try:
                    del app_sig[model_name]
                except KeyError:
                    raise SimulationFailure(
                        'Cannot delete the model "%s.%s" when deleting the '
                        'application. The model was not found in the '
                        'signature.'
                        % (app_label, model_name))

    def mutate(self, mutator):
        """Schedule an application deletion on the mutator.

        This will instruct the mutator to delete an application, if it exists.
        It will be scheduled and later executed on the database, if not
        optimized out.

        Args:
            mutator (django_evolution.mutators.AppMutator):
                The mutator to perform an operation on.
        """
        # This test will introduce a regression, but we can't afford to remove
        # all models at a same time if they aren't owned by the same database
        if mutator.database:
            app_sig = mutator.proj_sig[mutator.app_label]

            for model_name in app_sig.keys():
                mutation = DeleteModel(model_name)

                if mutation.is_mutable(mutator.app_label, mutator.proj_sig,
                                       mutator.database_sig,
                                       mutator.database):
                    mutator.run_mutation(mutation)

    def is_mutable(self, *args, **kwargs):
        """Return whether the mutation can be applied to the database.

        This will always return true. The mutation will safely handle the
        application no longer being around.

        Args:
            *args (tuple, unused):
                Positional arguments passed to the function.

            **kwargs (dict, unused):
                Keyword arguments passed to the function.

        Returns:
            bool:
            ``True``, always.
        """
        return True


class ChangeMeta(MutateModelField):
    """A mutation that changes meta proeprties on a model."""

    def __init__(self, model_name, prop_name, new_value):
        """Initialize the mutation.

        Args:
            model_name (unicode):
                The name of the model to change meta properties on.

            prop_name (unicode):
                The name of the property to change.

            new_value (object):
                The new value for the property.
        """
        super(ChangeMeta, self).__init__(model_name)
        self.prop_name = prop_name
        self.new_value = new_value

    def get_hint_params(self):
        """Return parameters for the mutation's hinted evolution.

        Returns:
            list of unicode:
            A list of parameter strings to pass to the mutation's constructor
            in a hinted evolution.
        """
        if self.prop_name in ('index_together', 'unique_together'):
            # Make sure these always appear as lists and not tuples, for
            # compatibility.
            norm_value = list(self.new_value)
        else:
            norm_value = self.new_value

        return [
            self.serialize_value(self.model_name),
            self.serialize_value(self.prop_name),
            repr(norm_value),
        ]

    def simulate(self, app_label, proj_sig, database_sig, database=None):
        """Simulate the mutation.

        This will alter the database schema to change metadata on the specified
        model.

        Args:
            app_label (unicode):
                The label for the Django application being mutated.

            proj_sig (dict):
                The project's schema signature.

            database_sig (dict):
                The database's schema signature.

            database (unicode, optional):
                The name of the database the operation is being performed on.

        Raises:
            django_evolution.errors.SimulationFailure:
                The simulation failed. The reason is in the exception's
                message.
        """
        try:
            app_sig = proj_sig[app_label]
        except KeyError:
            raise SimulationFailure(
                'Cannot change a meta property on model "%s.%s". The '
                'application could not be found in the signature.'
                % (app_label, self.model_name))

        try:
            model_sig = app_sig[self.model_name]
        except KeyError:
            raise SimulationFailure(
                'Cannot change a meta property on model "%s.%s". The model '
                'could not be found in the signature.'
                % (app_label, self.model_name))

        evolver = \
            EvolutionOperationsMulti(database, database_sig).get_evolver()

        if self.prop_name not in evolver.supported_change_meta:
            raise SimulationFailure(
                'ChangeMeta does not support modifying the "%s" '
                'attribute on "%s".'
                % (self.prop_name, self.model_name))

        model_sig['meta'][self.prop_name] = self.new_value

        if self.prop_name == 'unique_together':
            record_unique_together_applied(model_sig)

    def mutate(self, mutator, model):
        """Schedule a model meta property change on the mutator.

        This will instruct the mutator to change a meta property on a model. It
        will be scheduled and later executed on the database, if not optimized
        out.

        Args:
            mutator (django_evolution.mutators.ModelMutator):
                The mutator to perform an operation on.

            model (MockModel):
                The model being mutated.
        """
        mutator.change_meta(self, self.prop_name, self.new_value)
