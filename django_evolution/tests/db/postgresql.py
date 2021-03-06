from __future__ import unicode_literals

import django

from django_evolution.tests.utils import (make_generate_constraint_name,
                                          make_generate_index_name,
                                          make_generate_unique_constraint_name,
                                          test_connections)


django_version = django.VERSION[:2]

connection = test_connections['postgres']
generate_constraint_name = make_generate_constraint_name(connection)
generate_index_name = make_generate_index_name(connection)
generate_unique_constraint_name = \
    make_generate_unique_constraint_name(connection)


if django_version >= (2, 0):
    drop_index_sql = 'DROP INDEX IF EXISTS'
else:
    drop_index_sql = 'DROP INDEX'


add_field = {
    'AddNonNullNonCallableColumnModel': '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field" integer NOT NULL DEFAULT 1;',

        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "added_field" DROP DEFAULT;',
    ]),

    'AddNonNullCallableColumnModel': '\n'.join([
        'ALTER TABLE "tests_testmodel" ADD COLUMN "added_field" integer;',

        'UPDATE "tests_testmodel"'
        ' SET "added_field" = "int_field" WHERE "added_field" IS NULL;',

        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "added_field" SET NOT NULL;',
    ]),

    'AddNullColumnWithInitialColumnModel': '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field" integer NULL DEFAULT 1;',

        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "added_field" DROP DEFAULT;',
    ]),

    'AddStringColumnModel': '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field" varchar(10) NOT NULL'
        ' DEFAULT \'abc\\\'s xyz\';',

        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "added_field" DROP DEFAULT;',
    ]),

    'AddBlankStringColumnModel': '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field" varchar(10) NOT NULL DEFAULT \'\';',

        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "added_field" DROP DEFAULT;',
    ]),

    'AddDateColumnModel': '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field" timestamp with'
        ' time zone NOT NULL DEFAULT 2007-12-13 16:42:00;',

        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "added_field" DROP DEFAULT;',
    ]),

    'AddDefaultColumnModel': '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field" integer NOT NULL DEFAULT 42;',

        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "added_field" DROP DEFAULT;',
    ]),

    'AddMismatchInitialBoolColumnModel': '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field" boolean NOT NULL DEFAULT False;',

        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "added_field" DROP DEFAULT;',
    ]),

    'AddEmptyStringDefaultColumnModel': '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field" varchar(20) NOT NULL DEFAULT \'\';',

        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "added_field" DROP DEFAULT;',
    ]),

    'AddNullColumnModel': (
        'ALTER TABLE "tests_testmodel" ADD COLUMN "added_field" integer NULL;'
    ),

    'NonDefaultColumnModel': (
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "non-default_column" integer NULL;'
    ),

    'AddColumnCustomTableModel': (
        'ALTER TABLE "custom_table_name"'
        ' ADD COLUMN "added_field" integer NULL;'
    ),

    'AddIndexedColumnModel': '\n'.join([
        'ALTER TABLE "tests_testmodel" ADD COLUMN "add_field" integer NULL;',

        'CREATE INDEX "%s" ON "tests_testmodel" ("add_field");'
        % generate_index_name('tests_testmodel', 'add_field')
    ]),

    'AddUniqueColumnModel': (
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field" integer NULL UNIQUE;'
    ),

    'AddUniqueIndexedModel': (
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field" integer NULL UNIQUE;'
    ),

    'AddForeignKeyModel': '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field_id" integer NULL REFERENCES'
        ' "tests_addanchor1" ("id")  DEFERRABLE INITIALLY DEFERRED;',

        'CREATE INDEX "%s" ON "tests_testmodel" ("added_field_id");'
        % generate_index_name('tests_testmodel', 'added_field_id',
                              'added_field'),
    ]),
}

if django_version >= (1, 9):
    # Django 1.9+ no longer includes a UNIQUE keyword in the table creation,
    # instead creating these through constraints. It also brings back indexes.
    add_field.update({
        'AddManyToManyDatabaseTableModel': '\n'.join([
            'CREATE TABLE "tests_testmodel_added_field" '
            '("id" serial NOT NULL PRIMARY KEY,'
            ' "testmodel_id" integer NOT NULL,'
            ' "addanchor1_id" integer NOT NULL'
            ');',

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("testmodel_id")'
            ' REFERENCES "tests_testmodel" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('testmodel_id', 'id',
                                       'tests_testmodel_added_field',
                                       'tests_testmodel'),

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("addanchor1_id")'
            ' REFERENCES "tests_addanchor1" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('addanchor1_id', 'id',
                                       'tests_testmodel_added_field',
                                       'tests_addanchor1'),

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" UNIQUE ("testmodel_id", "addanchor1_id");'
            % generate_unique_constraint_name(
                'tests_testmodel_added_field',
                ['testmodel_id', 'addanchor1_id']),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("testmodel_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'testmodel_id'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("addanchor1_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'addanchor1_id'),
        ]),

        'AddManyToManyNonDefaultDatabaseTableModel': '\n'.join([
            'CREATE TABLE "tests_testmodel_added_field" '
            '("id" serial NOT NULL PRIMARY KEY,'
            ' "testmodel_id" integer NOT NULL,'
            ' "addanchor2_id" integer NOT NULL'
            ');',

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("testmodel_id")'
            ' REFERENCES "tests_testmodel" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('testmodel_id', 'id',
                                       'tests_testmodel_added_field',
                                       'tests_testmodel'),

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("addanchor2_id")'
            ' REFERENCES "custom_add_anchor_table" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('addanchor2_id', 'id',
                                       'tests_testmodel_added_field',
                                       'custom_add_anchor_table'),

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" UNIQUE ("testmodel_id", "addanchor2_id");'
            % generate_unique_constraint_name(
                'tests_testmodel_added_field',
                ['testmodel_id', 'addanchor2_id']),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("testmodel_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'testmodel_id'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("addanchor2_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'addanchor2_id'),
        ]),

        'AddManyToManySelf': '\n'.join([
            'CREATE TABLE "tests_testmodel_added_field" '
            '("id" serial NOT NULL PRIMARY KEY,'
            ' "from_testmodel_id" integer NOT NULL,'
            ' "to_testmodel_id" integer NOT NULL'
            ');',

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("from_testmodel_id")'
            ' REFERENCES "tests_testmodel" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('from_testmodel_id', 'id',
                                       'tests_testmodel_added_field',
                                       'tests_testmodel'),

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("to_testmodel_id")'
            ' REFERENCES "tests_testmodel" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('to_testmodel_id', 'id',
                                       'tests_testmodel_added_field',
                                       'tests_testmodel'),

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" UNIQUE'
            ' ("from_testmodel_id", "to_testmodel_id");'
            % generate_unique_constraint_name(
                'tests_testmodel_added_field',
                ['from_testmodel_id', 'to_testmodel_id']),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("from_testmodel_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'from_testmodel_id'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("to_testmodel_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'to_testmodel_id'),
        ]),
    })
elif django_version == (1, 8):
    # Django 1.8+ no longer creates indexes for the ForeignKeys on the
    # ManyToMany table.
    add_field.update({
        'AddManyToManyDatabaseTableModel': '\n'.join([
            'CREATE TABLE "tests_testmodel_added_field" '
            '("id" serial NOT NULL PRIMARY KEY,'
            ' "testmodel_id" integer NOT NULL,'
            ' "addanchor1_id" integer NOT NULL,'
            ' UNIQUE ("testmodel_id", "addanchor1_id")'
            ');',

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("testmodel_id")'
            ' REFERENCES "tests_testmodel" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('testmodel_id', 'id',
                                       'tests_testmodel_added_field',
                                       'tests_testmodel'),

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("addanchor1_id")'
            ' REFERENCES "tests_addanchor1" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('addanchor1_id', 'id',
                                       'tests_testmodel_added_field',
                                       'tests_addanchor1'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("testmodel_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'testmodel_id'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("addanchor1_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'addanchor1_id'),
        ]),

        'AddManyToManyNonDefaultDatabaseTableModel': '\n'.join([
            'CREATE TABLE "tests_testmodel_added_field" '
            '("id" serial NOT NULL PRIMARY KEY,'
            ' "testmodel_id" integer NOT NULL,'
            ' "addanchor2_id" integer NOT NULL,'
            ' UNIQUE ("testmodel_id", "addanchor2_id")'
            ');',

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("testmodel_id")'
            ' REFERENCES "tests_testmodel" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('testmodel_id', 'id',
                                       'tests_testmodel_added_field',
                                       'tests_testmodel'),

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("addanchor2_id")'
            ' REFERENCES "custom_add_anchor_table" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('addanchor2_id', 'id',
                                       'tests_testmodel_added_field',
                                       'custom_add_anchor_table'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("testmodel_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'testmodel_id'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("addanchor2_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'addanchor2_id'),
        ]),

        'AddManyToManySelf': '\n'.join([
            'CREATE TABLE "tests_testmodel_added_field" '
            '("id" serial NOT NULL PRIMARY KEY,'
            ' "from_testmodel_id" integer NOT NULL,'
            ' "to_testmodel_id" integer NOT NULL,'
            ' UNIQUE ("from_testmodel_id", "to_testmodel_id")'
            ');',

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("from_testmodel_id")'
            ' REFERENCES "tests_testmodel" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('from_testmodel_id', 'id',
                                       'tests_testmodel_added_field',
                                       'tests_testmodel'),

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("to_testmodel_id")'
            ' REFERENCES "tests_testmodel" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('to_testmodel_id', 'id',
                                       'tests_testmodel_added_field',
                                       'tests_testmodel'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("from_testmodel_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'from_testmodel_id'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("to_testmodel_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'to_testmodel_id'),
        ]),
    })
elif django_version >= (1, 7):
    # Django 1.7 introduced more condensed CREATE TABLE statements, and
    # indexes for fields on the model. (The indexes were removed for Postgres
    # in subsequent releases.)
    add_field.update({
        'AddManyToManyDatabaseTableModel': '\n'.join([
            'CREATE TABLE "tests_testmodel_added_field" '
            '("id" serial NOT NULL PRIMARY KEY,'
            ' "testmodel_id" integer NOT NULL,'
            ' "addanchor1_id" integer NOT NULL,'
            ' UNIQUE ("testmodel_id", "addanchor1_id")'
            ');',

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("testmodel_id")'
            ' REFERENCES "tests_testmodel" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('testmodel_id', 'id',
                                       'tests_testmodel_added_field',
                                       'tests_testmodel'),

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("addanchor1_id")'
            ' REFERENCES "tests_addanchor1" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('addanchor1_id', 'id',
                                       'tests_testmodel_added_field',
                                       'tests_addanchor1'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("testmodel_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'testmodel_id'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("addanchor1_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'addanchor1_id'),
        ]),

        'AddManyToManyNonDefaultDatabaseTableModel': '\n'.join([
            'CREATE TABLE "tests_testmodel_added_field" '
            '("id" serial NOT NULL PRIMARY KEY,'
            ' "testmodel_id" integer NOT NULL,'
            ' "addanchor2_id" integer NOT NULL,'
            ' UNIQUE ("testmodel_id", "addanchor2_id")'
            ');',

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("testmodel_id")'
            ' REFERENCES "tests_testmodel" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('testmodel_id', 'id',
                                       'tests_testmodel_added_field',
                                       'tests_testmodel'),

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("addanchor2_id")'
            ' REFERENCES "custom_add_anchor_table" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('addanchor2_id', 'id',
                                       'tests_testmodel_added_field',
                                       'custom_add_anchor_table'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("testmodel_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'testmodel_id'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("addanchor2_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'addanchor2_id'),
        ]),

        'AddManyToManySelf': '\n'.join([
            'CREATE TABLE "tests_testmodel_added_field" '
            '("id" serial NOT NULL PRIMARY KEY,'
            ' "from_testmodel_id" integer NOT NULL,'
            ' "to_testmodel_id" integer NOT NULL,'
            ' UNIQUE ("from_testmodel_id", "to_testmodel_id")'
            ');',

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("from_testmodel_id")'
            ' REFERENCES "tests_testmodel" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('from_testmodel_id', 'id',
                                       'tests_testmodel_added_field',
                                       'tests_testmodel'),

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("to_testmodel_id")'
            ' REFERENCES "tests_testmodel" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('to_testmodel_id', 'id',
                                       'tests_testmodel_added_field',
                                       'tests_testmodel'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("from_testmodel_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'from_testmodel_id'),

            'CREATE INDEX "%s" ON'
            ' "tests_testmodel_added_field" ("to_testmodel_id");'
            % generate_index_name('tests_testmodel_added_field',
                                  'to_testmodel_id'),
        ]),
    })
else:
    add_field.update({
        'AddManyToManyDatabaseTableModel': '\n'.join([
            'CREATE TABLE "tests_testmodel_added_field" (',
            '    "id" serial NOT NULL PRIMARY KEY,',
            '    "testmodel_id" integer NOT NULL,',
            '    "addanchor1_id" integer NOT NULL,',
            '    UNIQUE ("testmodel_id", "addanchor1_id")',
            ')',
            ';',

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("addanchor1_id")'
            ' REFERENCES "tests_addanchor1" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('addanchor1_id', 'id',
                                       'tests_testmodel_added_field',
                                       'tests_addanchor1'),

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("testmodel_id")'
            ' REFERENCES "tests_testmodel" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('testmodel_id', 'id',
                                       'tests_testmodel_added_field',
                                       'tests_testmodel'),
        ]),

        'AddManyToManyNonDefaultDatabaseTableModel': '\n'.join([
            'CREATE TABLE "tests_testmodel_added_field" (',
            '    "id" serial NOT NULL PRIMARY KEY,',
            '    "testmodel_id" integer NOT NULL,',
            '    "addanchor2_id" integer NOT NULL,',
            '    UNIQUE ("testmodel_id", "addanchor2_id")',
            ')',
            ';',

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("addanchor2_id")'
            ' REFERENCES "custom_add_anchor_table" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('addanchor2_id', 'id',
                                       'tests_testmodel_added_field',
                                       'custom_add_anchor_table'),

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("testmodel_id")'
            ' REFERENCES "tests_testmodel" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('testmodel_id', 'id',
                                       'tests_testmodel_added_field',
                                       'tests_testmodel'),
        ]),

        'AddManyToManySelf': '\n'.join([
            'CREATE TABLE "tests_testmodel_added_field" (',
            '    "id" serial NOT NULL PRIMARY KEY,',
            '    "from_testmodel_id" integer NOT NULL,',
            '    "to_testmodel_id" integer NOT NULL,',
            '    UNIQUE ("from_testmodel_id", "to_testmodel_id")',
            ')',
            ';',

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("from_testmodel_id")'
            ' REFERENCES "tests_testmodel" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('from_testmodel_id', 'id',
                                       'tests_testmodel_added_field',
                                       'tests_testmodel'),

            'ALTER TABLE "tests_testmodel_added_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("to_testmodel_id")'
            ' REFERENCES "tests_testmodel" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('to_testmodel_id', 'id',
                                       'tests_testmodel_added_field',
                                       'tests_testmodel'),
        ]),
    })

delete_field = {
    'DefaultNamedColumnModel': (
        'ALTER TABLE "tests_testmodel" DROP COLUMN "int_field" CASCADE;'
    ),

    'NonDefaultNamedColumnModel': (
        'ALTER TABLE "tests_testmodel"'
        ' DROP COLUMN "non-default_db_column" CASCADE;'
    ),

    'ConstrainedColumnModel': (
        'ALTER TABLE "tests_testmodel" DROP COLUMN "int_field3" CASCADE;'
    ),

    'DefaultManyToManyModel': (
        'DROP TABLE "tests_testmodel_m2m_field1";'
    ),

    'NonDefaultManyToManyModel': (
        'DROP TABLE "non-default_m2m_table";'
    ),

    'DeleteForeignKeyModel': (
        'ALTER TABLE "tests_testmodel" DROP COLUMN "fk_field1_id" CASCADE;'
    ),

    'DeleteColumnCustomTableModel': (
        'ALTER TABLE "custom_table_name" DROP COLUMN "value" CASCADE;'
    ),
}

change_field = {
    "SetNotNullChangeModelWithConstant": '\n'.join([
        'UPDATE "tests_testmodel"'
        ' SET "char_field1" = \'abc\\\'s xyz\' WHERE "char_field1" IS NULL;',

        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "char_field1" SET NOT NULL;',
    ]),

    "SetNotNullChangeModelWithCallable": '\n'.join([
        'UPDATE "tests_testmodel"'
        ' SET "char_field1" = "char_field" WHERE "char_field1" IS NULL;',

        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "char_field1" SET NOT NULL;',
    ]),

    "SetNullChangeModel": (
        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "char_field2" DROP NOT NULL;'
    ),

    "NoOpChangeModel": '',

    "IncreasingMaxLengthChangeModel": (
        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "char_field" TYPE varchar(45)'
        ' USING CAST("char_field" as varchar(45));'
    ),

    "DecreasingMaxLengthChangeModel": (
        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "char_field" TYPE varchar(1)'
        ' USING CAST("char_field" as varchar(1));'
    ),

    "DBColumnChangeModel": (
        'ALTER TABLE "tests_testmodel"'
        ' RENAME COLUMN "custom_db_column" TO "customised_db_column";'
    ),

    "AddDBIndexChangeModel": (
        'CREATE INDEX "%s" ON "tests_testmodel" ("int_field2");'
        % generate_index_name('tests_testmodel', 'int_field2')
    ),

    'AddDBIndexNoOpChangeModel': '',

    "RemoveDBIndexChangeModel": (
        '%s "%s";'
        % (drop_index_sql,
           generate_index_name('tests_testmodel', 'int_field1'))
    ),

    'RemoveDBIndexNoOpChangeModel': '',

    "AddUniqueChangeModel": (
        'ALTER TABLE "tests_testmodel"'
        ' ADD CONSTRAINT "%s" UNIQUE("int_field4");'
        % generate_unique_constraint_name('tests_testmodel', ['int_field4'])
    ),

    "RemoveUniqueChangeModel": (
        'ALTER TABLE "tests_testmodel"'
        ' DROP CONSTRAINT "tests_testmodel_int_field3_key";'
    ),

    "MultiAttrChangeModel": '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "char_field2" DROP NOT NULL;',

        'ALTER TABLE "tests_testmodel"'
        ' RENAME COLUMN "custom_db_column" TO "custom_db_column2";',

        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "char_field" TYPE varchar(35)'
        ' USING CAST("char_field" as varchar(35));',
    ]),

    "MultiAttrSingleFieldChangeModel": '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "char_field2" TYPE varchar(35)'
        ' USING CAST("char_field2" as varchar(35)),'
        ' ALTER COLUMN "char_field2" DROP NOT NULL;',
    ]),

    "RedundantAttrsChangeModel": '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "char_field2" DROP NOT NULL;',

        'ALTER TABLE "tests_testmodel"'
        ' RENAME COLUMN "custom_db_column" TO "custom_db_column3";',

        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "char_field" TYPE varchar(35)'
        ' USING CAST("char_field" as varchar(35));',
    ]),
}

if django_version >= (1, 11):
    change_field.update({
        'M2MDBTableChangeModel': '\n'.join([
            'SET CONSTRAINTS "%(constraint)s" IMMEDIATE;'
            ' ALTER TABLE "change_field_non-default_m2m_table"'
            ' DROP CONSTRAINT "%(constraint)s";'
            % {
                'constraint': generate_constraint_name(
                    'testmodel_id', 'my_id',
                    'change_field_non-default_m2m_table',
                    'tests_testmodel'),
            },

            'ALTER TABLE "change_field_non-default_m2m_table"'
            ' RENAME TO "custom_m2m_db_table_name";',

            'ALTER TABLE "custom_m2m_db_table_name"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("testmodel_id")'
            ' REFERENCES "tests_testmodel" ("my_id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('testmodel_id', 'my_id',
                                       'custom_m2m_db_table_name',
                                       'tests_testmodel'),
        ]),
    })
else:
    change_field.update({
        'M2MDBTableChangeModel': '\n'.join([
            'ALTER TABLE "change_field_non-default_m2m_table"'
            ' DROP CONSTRAINT "%s";'
            % generate_constraint_name('testmodel_id', 'my_id',
                                       'change_field_non-default_m2m_table',
                                       'tests_testmodel'),

            'ALTER TABLE "change_field_non-default_m2m_table"'
            ' RENAME TO "custom_m2m_db_table_name";',

            'ALTER TABLE "custom_m2m_db_table_name"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("testmodel_id")'
            ' REFERENCES "tests_testmodel" ("my_id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('testmodel_id', 'my_id',
                                       'custom_m2m_db_table_name',
                                       'tests_testmodel'),
        ]),
    })


delete_model = {
    'BasicModel': (
        'DROP TABLE "tests_basicmodel";'
    ),

    'BasicWithM2MModel': '\n'.join([
        'DROP TABLE "tests_basicwithm2mmodel_m2m";',
        'DROP TABLE "tests_basicwithm2mmodel";'
    ]),

    'CustomTableModel': (
        'DROP TABLE "custom_table_name";'
    ),

    'CustomTableWithM2MModel': '\n'.join([
        'DROP TABLE "another_custom_table_name_m2m";',
        'DROP TABLE "another_custom_table_name";'
    ]),
}

rename_model = {
    'RenameModel': (
        'ALTER TABLE "tests_testmodel" RENAME TO "tests_destmodel";'
    ),
    'RenameModelSameTable': '',
    'RenameModelForeignKeys': (
        'ALTER TABLE "tests_testmodel" RENAME TO "tests_destmodel";'
    ),
    'RenameModelForeignKeysSameTable': '',
    'RenameModelManyToManyField': (
        'ALTER TABLE "tests_testmodel" RENAME TO "tests_destmodel";'
    ),
    'RenameModelManyToManyFieldSameTable': '',
}

delete_application = {
    'DeleteApplication': '\n'.join([
        'DROP TABLE "tests_testmodel_anchor_m2m";',
        'DROP TABLE "tests_testmodel";',
        'DROP TABLE "tests_appdeleteanchor1";',
        'DROP TABLE "app_delete_custom_add_anchor_table";',
        'DROP TABLE "app_delete_custom_table_name";',
    ]),

    'DeleteApplicationWithoutDatabase': "",
}

rename_field = {
    'RenameColumnModel': (
        'ALTER TABLE "tests_testmodel"'
        ' RENAME COLUMN "int_field" TO "renamed_field";'
    ),

    'RenameColumnWithTableNameModel': (
        'ALTER TABLE "tests_testmodel"'
        ' RENAME COLUMN "int_field" TO "renamed_field";'
    ),

    'RenameForeignKeyColumnModel': (
        'ALTER TABLE "tests_testmodel"'
        ' RENAME COLUMN "fk_field_id" TO "renamed_field_id";'
    ),

    'RenameNonDefaultColumnNameModel': (
        'ALTER TABLE "tests_testmodel"'
        ' RENAME COLUMN "custom_db_col_name" TO "renamed_field";'
    ),

    'RenameNonDefaultColumnNameToNonDefaultNameModel': (
        'ALTER TABLE "tests_testmodel"'
        ' RENAME COLUMN "custom_db_col_name" TO "non-default_column_name";'
    ),

    'RenameNonDefaultColumnNameToNonDefaultNameAndTableModel': (
        'ALTER TABLE "tests_testmodel"'
        ' RENAME COLUMN "custom_db_col_name" TO "non-default_column_name2";'
    ),

    'RenameColumnCustomTableModel': (
        'ALTER TABLE "custom_rename_table_name"'
        ' RENAME COLUMN "value" TO "renamed_field";'
    ),
}

if django_version >= (1, 11):
    rename_field.update({
        'RenameNonDefaultManyToManyTableModel': '\n'.join([
            'SET CONSTRAINTS "%(constraint)s" IMMEDIATE;'
            ' ALTER TABLE "non-default_db_table"'
            ' DROP CONSTRAINT "%(constraint)s";'
            % {
                'constraint': generate_constraint_name(
                    'testmodel_id', 'id', 'non-default_db_table',
                    'tests_testmodel'),
            },

            'ALTER TABLE "non-default_db_table"'
            ' RENAME TO "tests_testmodel_renamed_field";',

            'ALTER TABLE "tests_testmodel_renamed_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("testmodel_id")'
            ' REFERENCES "tests_testmodel" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('testmodel_id', 'id',
                                       'tests_testmodel_renamed_field',
                                       'tests_testmodel'),
        ]),

        'RenamePrimaryKeyColumnModel': '\n'.join([
            'SET CONSTRAINTS "%(constraint)s" IMMEDIATE;'
            ' ALTER TABLE "tests_testmodel_m2m_field"'
            ' DROP CONSTRAINT "%(constraint)s";'
            % {
                'constraint': generate_constraint_name(
                    'testmodel_id', 'id', 'tests_testmodel_m2m_field',
                    'tests_testmodel'),
            },

            'SET CONSTRAINTS "%(constraint)s" IMMEDIATE;'
            ' ALTER TABLE "non-default_db_table"'
            ' DROP CONSTRAINT "%(constraint)s";'
            % {
                'constraint': generate_constraint_name('testmodel_id', 'id',
                                                       'non-default_db_table',
                                                       'tests_testmodel'),
            },

            'ALTER TABLE "tests_testmodel" RENAME COLUMN "id" TO "my_pk_id";',

            'ALTER TABLE "tests_testmodel_m2m_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("testmodel_id")'
            ' REFERENCES "tests_testmodel" ("my_pk_id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('testmodel_id', 'my_pk_id',
                                       'tests_testmodel_m2m_field',
                                       'tests_testmodel'),

            'ALTER TABLE "non-default_db_table"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("testmodel_id")'
            ' REFERENCES "tests_testmodel" ("my_pk_id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('testmodel_id', 'my_pk_id',
                                       'non-default_db_table',
                                       'tests_testmodel'),
        ]),

        'RenameManyToManyTableModel': '\n'.join([
            'SET CONSTRAINTS "%(constraint)s" IMMEDIATE;'
            ' ALTER TABLE "tests_testmodel_m2m_field"'
            ' DROP CONSTRAINT "%(constraint)s";'
            % {
                'constraint': generate_constraint_name(
                    'testmodel_id', 'id', 'tests_testmodel_m2m_field',
                    'tests_testmodel'),
            },

            'ALTER TABLE "tests_testmodel_m2m_field"'
            ' RENAME TO "tests_testmodel_renamed_field";',

            'ALTER TABLE "tests_testmodel_renamed_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("testmodel_id")'
            ' REFERENCES "tests_testmodel" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('testmodel_id', 'id',
                                       'tests_testmodel_renamed_field',
                                       'tests_testmodel'),
        ]),

        'RenameManyToManyTableWithColumnNameModel': '\n'.join([
            'SET CONSTRAINTS "%(constraint)s" IMMEDIATE;'
            ' ALTER TABLE "tests_testmodel_m2m_field"'
            ' DROP CONSTRAINT "%(constraint)s";'
            % {
                'constraint': generate_constraint_name(
                    'testmodel_id', 'id', 'tests_testmodel_m2m_field',
                    'tests_testmodel'),
            },

            'ALTER TABLE "tests_testmodel_m2m_field"'
            ' RENAME TO "tests_testmodel_renamed_field";',

            'ALTER TABLE "tests_testmodel_renamed_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("testmodel_id")'
            ' REFERENCES "tests_testmodel" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('testmodel_id', 'id',
                                       'tests_testmodel_renamed_field',
                                       'tests_testmodel'),
        ]),
    })
else:
    rename_field.update({
        'RenameNonDefaultManyToManyTableModel': '\n'.join([
            'ALTER TABLE "non-default_db_table"'
            ' DROP CONSTRAINT "%s";'
            % generate_constraint_name('testmodel_id', 'id',
                                       'non-default_db_table',
                                       'tests_testmodel'),

            'ALTER TABLE "non-default_db_table"'
            ' RENAME TO "tests_testmodel_renamed_field";',

            'ALTER TABLE "tests_testmodel_renamed_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("testmodel_id")'
            ' REFERENCES "tests_testmodel" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('testmodel_id', 'id',
                                       'tests_testmodel_renamed_field',
                                       'tests_testmodel'),
        ]),

        'RenamePrimaryKeyColumnModel': '\n'.join([
            'ALTER TABLE "tests_testmodel_m2m_field" DROP CONSTRAINT "%s";'
            % generate_constraint_name('testmodel_id', 'id',
                                       'tests_testmodel_m2m_field',
                                       'tests_testmodel'),

            'ALTER TABLE "non-default_db_table"' ' DROP CONSTRAINT "%s";'
            % generate_constraint_name('testmodel_id', 'id',
                                       'non-default_db_table',
                                       'tests_testmodel'),

            'ALTER TABLE "tests_testmodel" RENAME COLUMN "id" TO "my_pk_id";',

            'ALTER TABLE "tests_testmodel_m2m_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("testmodel_id")'
            ' REFERENCES "tests_testmodel" ("my_pk_id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('testmodel_id', 'my_pk_id',
                                       'tests_testmodel_m2m_field',
                                       'tests_testmodel'),

            'ALTER TABLE "non-default_db_table"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("testmodel_id")'
            ' REFERENCES "tests_testmodel" ("my_pk_id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('testmodel_id', 'my_pk_id',
                                       'non-default_db_table',
                                       'tests_testmodel'),
        ]),

        'RenameManyToManyTableModel': '\n'.join([
            'ALTER TABLE "tests_testmodel_m2m_field" DROP CONSTRAINT "%s";'
            % generate_constraint_name('testmodel_id', 'id',
                                       'tests_testmodel_m2m_field',
                                       'tests_testmodel'),

            'ALTER TABLE "tests_testmodel_m2m_field"'
            ' RENAME TO "tests_testmodel_renamed_field";',

            'ALTER TABLE "tests_testmodel_renamed_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("testmodel_id")'
            ' REFERENCES "tests_testmodel" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('testmodel_id', 'id',
                                       'tests_testmodel_renamed_field',
                                       'tests_testmodel'),
        ]),

        'RenameManyToManyTableWithColumnNameModel': '\n'.join([
            'ALTER TABLE "tests_testmodel_m2m_field" DROP CONSTRAINT "%s";'
            % generate_constraint_name('testmodel_id', 'id',
                                       'tests_testmodel_m2m_field',
                                       'tests_testmodel'),

            'ALTER TABLE "tests_testmodel_m2m_field"'
            ' RENAME TO "tests_testmodel_renamed_field";',

            'ALTER TABLE "tests_testmodel_renamed_field"'
            ' ADD CONSTRAINT "%s" FOREIGN KEY ("testmodel_id")'
            ' REFERENCES "tests_testmodel" ("id")'
            ' DEFERRABLE INITIALLY DEFERRED;'
            % generate_constraint_name('testmodel_id', 'id',
                                       'tests_testmodel_renamed_field',
                                       'tests_testmodel'),
        ]),
    })

sql_mutation = {
    'AddFirstTwoFields': '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field1" integer NULL;',

        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field2" integer NULL;'
    ]),

    'AddThirdField': (
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field3" integer NULL;'
    ),

    'SQLMutationOutput': '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field1" integer NULL;',

        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field2" integer NULL;',

        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field3" integer NULL;',
    ]),
}

generics = {
    'DeleteColumnModel': (
        'ALTER TABLE "tests_testmodel" DROP COLUMN "char_field" CASCADE;'
    ),
}

inheritance = {
    'AddToChildModel': '\n'.join([
        'ALTER TABLE "tests_childmodel"'
        ' ADD COLUMN "added_field" integer  DEFAULT 42;',

        'ALTER TABLE "tests_childmodel"'
        ' ALTER COLUMN "added_field" DROP DEFAULT;',

        'ALTER TABLE "tests_childmodel"'
        ' ALTER COLUMN "added_field" SET NOT NULL;',
    ]),

    'DeleteFromChildModel': (
        'ALTER TABLE "tests_childmodel" DROP COLUMN "int_field" CASCADE;'
    ),
}

unique_together = {
    'setting_from_empty': (
        'CREATE UNIQUE INDEX "%s"'
        ' ON "tests_testmodel" ("int_field1", "char_field1");'
        % generate_unique_constraint_name('tests_testmodel',
                                          ['int_field1', 'char_field1'])
    ),

    'append_list': (
        'CREATE UNIQUE INDEX "%s"'
        ' ON "tests_testmodel" ("int_field2", "char_field2");'
        % generate_unique_constraint_name('tests_testmodel',
                                          ['int_field2', 'char_field2'])
    ),

    'set_remove': (
        'CREATE UNIQUE INDEX "%s"'
        ' ON "tests_testmodel" ("int_field1", "char_field1");'
        % generate_unique_constraint_name('tests_testmodel',
                                          ['int_field1', 'char_field1'])
    ),

    'ignore_missing_indexes': (
        'CREATE UNIQUE INDEX "%s"'
        ' ON "tests_testmodel" ("char_field1", "char_field2");'
        % generate_unique_constraint_name('tests_testmodel',
                                          ['char_field1', 'char_field2'])
    ),

    'upgrade_from_v1_sig': (
        'CREATE UNIQUE INDEX "%s"'
        ' ON "tests_testmodel" ("int_field1", "char_field1");'
        % generate_unique_constraint_name('tests_testmodel',
                                          ['int_field1', 'char_field1'])
    ),
}

if django_version >= (1, 9):
    # In Django >= 1.9, unique_together indexes are created specifically
    # after table creation, using Django's generated constraint names.
    unique_together.update({
        'removing': (
            'ALTER TABLE "tests_testmodel" DROP CONSTRAINT "%s";'
            % generate_unique_constraint_name('tests_testmodel',
                                              ['int_field1', 'char_field1'])
        ),

        'replace_list': '\n'.join([
            'ALTER TABLE "tests_testmodel" DROP CONSTRAINT "%s";'
            % generate_unique_constraint_name('tests_testmodel',
                                              ['int_field1', 'char_field1']),

            'CREATE UNIQUE INDEX "%s"'
            ' ON "tests_testmodel" ("int_field2", "char_field2");'
            % generate_unique_constraint_name('tests_testmodel',
                                              ['int_field2', 'char_field2']),
        ]),
    })
else:
    # In Django < 1.9, unique_together indexes are created during table
    # creation, using Postgres's default naming scheme, instead of using a
    # generated name, so we need to drop with those hard-coded names.
    unique_together.update({
        'removing': (
            'ALTER TABLE "tests_testmodel"'
            ' DROP CONSTRAINT "tests_testmodel_int_field1_char_field1_key";'
        ),

        'replace_list': '\n'.join([
            'ALTER TABLE "tests_testmodel"'
            ' DROP CONSTRAINT "tests_testmodel_int_field1_char_field1_key";',

            'CREATE UNIQUE INDEX "%s"'
            ' ON "tests_testmodel" ("int_field2", "char_field2");'
            % generate_unique_constraint_name('tests_testmodel',
                                              ['int_field2', 'char_field2']),
        ]),
    })

index_together = {
    'setting_from_empty': '\n'.join([
        'CREATE INDEX "%s"'
        ' ON "tests_testmodel" ("int_field1", "char_field1");'
        % generate_index_name('tests_testmodel',
                              ['int_field1', 'char_field1'],
                              index_together=True)
    ]),

    'replace_list': '\n'.join([
        '%s "%s";'
        % (drop_index_sql,
           generate_index_name('tests_testmodel',
                               ['int_field1', 'char_field1'],
                               index_together=True)),

        'CREATE INDEX "%s"'
        ' ON "tests_testmodel" ("int_field2", "char_field2");'
        % generate_index_name('tests_testmodel',
                              ['int_field2', 'char_field2'],
                              index_together=True),
    ]),

    'append_list': '\n'.join([
        'CREATE INDEX "%s"'
        ' ON "tests_testmodel" ("int_field2", "char_field2");'
        % generate_index_name('tests_testmodel',
                              ['int_field2', 'char_field2'],
                              index_together=True),
    ]),

    'removing': '\n'.join([
        '%s "%s";'
        % (drop_index_sql,
           generate_index_name('tests_testmodel',
                               ['int_field1', 'char_field1'],
                               index_together=True)),
    ]),

    'ignore_missing_indexes': (
        'CREATE INDEX "%s"'
        ' ON "tests_testmodel" ("char_field1", "char_field2");'
        % generate_index_name('tests_testmodel',
                              ['char_field1', 'char_field2'],
                              index_together=True)
    ),
}

indexes = {
    'replace_list': '\n'.join([
        '%s "%s";'
        % (drop_index_sql,
           generate_index_name('tests_testmodel', ['int_field1'],
                               model_meta_indexes=True)),

        '%s "my_custom_index";'
        % drop_index_sql,

        'CREATE INDEX "%s"'
        ' ON "tests_testmodel" ("int_field2");'
        % generate_index_name('tests_testmodel', ['int_field2'],
                              model_meta_indexes=True),
    ]),

    'append_list': '\n'.join([
        'CREATE INDEX "%s"'
        ' ON "tests_testmodel" ("int_field2");'
        % generate_index_name('tests_testmodel', ['int_field2'],
                              model_meta_indexes=True),
    ]),

    'removing': '\n'.join([
        '%s "%s";'
        % (drop_index_sql,
           generate_index_name('tests_testmodel', ['int_field1'],
                               model_meta_indexes=True)),

        '%s "my_custom_index";'
        % drop_index_sql,
    ]),

    'ignore_missing_indexes': (
        'CREATE INDEX "%s"'
        ' ON "tests_testmodel" ("int_field2");'
        % generate_index_name('tests_testmodel', ['int_field2'],
                              model_meta_indexes=True)
    ),
}

if django.VERSION[:2] >= (2, 0):
    indexes.update({
        'setting_from_empty': '\n'.join([
            'CREATE INDEX "%s"'
            ' ON "tests_testmodel" ("int_field1");'
            % generate_index_name('tests_testmodel',
                                  ['int_field1'],
                                  model_meta_indexes=True),

            'CREATE INDEX "my_custom_index"'
            ' ON "tests_testmodel" ("char_field1", "char_field2"DESC);',
        ]),
    })
else:
    indexes.update({
        'setting_from_empty': '\n'.join([
            'CREATE INDEX "%s"'
            ' ON "tests_testmodel" ("int_field1");'
            % generate_index_name('tests_testmodel',
                                  ['int_field1'],
                                  model_meta_indexes=True),

            'CREATE INDEX "my_custom_index"'
            ' ON "tests_testmodel" ("char_field1", "char_field2" DESC);',
        ]),
    })

preprocessing = {
    'add_change_field': '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field" varchar(50) NULL DEFAULT \'bar\';',

        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "added_field" DROP DEFAULT;',
    ]),

    'add_change_rename_field': '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "renamed_field" varchar(50) NULL DEFAULT \'bar\';',

        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "renamed_field" DROP DEFAULT;',
    ]),

    'add_delete_add_field': '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field" integer NOT NULL DEFAULT 42;',

        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "added_field" DROP DEFAULT;',
    ]),

    'add_delete_add_rename_field': '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "renamed_field" integer NOT NULL DEFAULT 42;',

        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "renamed_field" DROP DEFAULT;',
    ]),

    'add_rename_change_field': '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "renamed_field" varchar(50) NULL DEFAULT \'bar\';',

        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "renamed_field" DROP DEFAULT;',
    ]),

    'add_rename_change_rename_change_field': '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "renamed_field" varchar(50) NULL DEFAULT \'foo\';',

        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "renamed_field" DROP DEFAULT;',
    ]),

    'add_rename_field_with_db_column': (
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field" varchar(50) NULL;'
    ),

    'add_field_rename_model': '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field_id" integer NULL REFERENCES'
        ' "tests_reffedpreprocmodel" ("id")  DEFERRABLE INITIALLY DEFERRED;',

        'CREATE INDEX "%s" ON "tests_testmodel" ("added_field_id");'
        % generate_index_name('tests_testmodel', 'added_field_id',
                              'added_field'),
    ]),

    'add_rename_field_rename_model': '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "renamed_field_id" integer NULL REFERENCES'
        ' "tests_reffedpreprocmodel" ("id")  DEFERRABLE INITIALLY DEFERRED;',

        'CREATE INDEX "%s" ON "tests_testmodel" ("renamed_field_id");'
        % generate_index_name('tests_testmodel', 'renamed_field_id',
                              'renamed_field'),
    ]),

    'add_sql_delete': '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "added_field" varchar(20) NOT NULL DEFAULT \'foo\';',

        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "added_field" DROP DEFAULT;',

        '-- Comment --',

        'ALTER TABLE "tests_testmodel" DROP COLUMN "added_field" CASCADE;',
    ]),

    'change_rename_field': '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "char_field" DROP NOT NULL;',

        'ALTER TABLE "tests_testmodel"'
        ' RENAME COLUMN "char_field" TO "renamed_field";',
    ]),

    'change_rename_change_rename_field': '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "char_field" TYPE varchar(30)'
        ' USING CAST("char_field" as varchar(30)),'
        ' ALTER COLUMN "char_field" DROP NOT NULL;',

        'ALTER TABLE "tests_testmodel"'
        ' RENAME COLUMN "char_field" TO "renamed_field";',
    ]),

    'delete_char_field': (
        'ALTER TABLE "tests_testmodel" DROP COLUMN "char_field" CASCADE;'
    ),

    'rename_add_field': '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' RENAME COLUMN "char_field" TO "renamed_field";',

        'ALTER TABLE "tests_testmodel"'
        ' ADD COLUMN "char_field" varchar(50) NULL;',
    ]),

    'rename_change_rename_change_field': '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' RENAME COLUMN "char_field" TO "renamed_field";',

        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "renamed_field" TYPE varchar(50)'
        ' USING CAST("renamed_field" as varchar(50)),'
        ' ALTER COLUMN "renamed_field" DROP NOT NULL;',
    ]),

    'rename_rename_field': '\n'.join([
        'ALTER TABLE "tests_testmodel"'
        ' RENAME COLUMN "char_field" TO "renamed_field";',
    ]),

    'rename_delete_model': (
        'DROP TABLE "tests_testmodel";'
    ),

    'noop': '',
}


evolver = {
    'evolve_app_task': (
        'ALTER TABLE "tests_testmodel"'
        ' ALTER COLUMN "value" TYPE varchar(100)'
        ' USING CAST("value" as varchar(100));'
    ),

    'purge_app_task': (
        'DROP TABLE "tests_testmodel";'
    ),
}
