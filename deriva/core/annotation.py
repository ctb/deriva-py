"""Definitions and implementation for validating ERMrest schema annotations."""

import json
import logging
import pkgutil
import jsonschema

from .. import core
from .ermrest_model import tag

logger = logging.getLogger(__name__)


class _AnnotationSchemas (object):
    """Container of annotation schemas."""

    # TODO: inherit from 'collections.abc.Mapping'

    def __init__(self):
        super(_AnnotationSchemas, self).__init__()
        self._abbrev = dict((v, k) for k, v in tag.items())
        self._schemas = {}

    def __getitem__(self, key):
        try:
            return self._schemas[key]
        except KeyError:
            abbrev = self._abbrev[key]  # let this raise a 'KeyError' if the tag name is unknown
            s = pkgutil.get_data(core.__name__, 'schemas/%s.schema.json' % abbrev).decode()
            v = json.loads(s)
            self._schemas[key] = v
            return v

    def __iter__(self):
        return iter(self._schemas)

    def __len__(self):
        return len(self._schemas)


_schemas = _AnnotationSchemas()
_schema_store = {  # the schema store for the schema resolver, stores all schemas that are extended
    _schemas[tag_name]['$id']: _schemas[tag_name] for tag_name in [tag.export, tag.source_definitions]
}
_nop = lambda validator, value, instance, schema: None


def validate(model_obj, tag_name=None):
    """Validate the annotation(s) of the model object.

    :param model_obj: model object container of annotations
    :param tag_name: tag name of the annotation to validate, if none, will validate all known annotations
    :return: a list of validation errors, if any
    """
    if not tag_name:
        errors = []
        for tag_name in model_obj.annotations:
            logger.info("Validating against schema for %s" % tag_name)
            errors.extend(_validate(model_obj, tag_name))
        return errors
    else:
        return _validate(model_obj, tag_name)


def _validate(model_obj, tag_name):
    """Validate an annotation of the model object.

    :param model_obj: model object container of annotations
    :param tag_name: tag name of the annotation to validate
    :return: a list of validation errors, if any
    """
    try:
        if tag_name in model_obj.annotations:
            schema = _schemas[tag_name]
            resolver = jsonschema.RefResolver.from_schema(schema, store=_schema_store)
            ExtendedValidator = jsonschema.validators.extend(
                jsonschema.Draft7Validator,
                {
                    'valid-columns': _validate_columns_fn(model_obj),
                    'valid-source-key': _validate_source_key_fn(model_obj),
                    'valid-source-entry': _validate_source_entry_fn(model_obj),
                    'valid-foreign-keys': _validate_foreign_keys_fn(model_obj),
                    'valid-sort-key': _validate_sort_key_fn(model_obj)
                }
            )
            validator = ExtendedValidator(schema, resolver=resolver)
            validator.validate(model_obj.annotations[tag_name])
            # TODO: make standard validator an option
            #  jsonschema.validate(model_obj.annotations[tag_name], schema, resolver=resolver)
    except jsonschema.ValidationError as e:
        logger.error(e)
        return [e]
    except KeyError as e:
        msg = 'Unknown annotation tag name "%s"' % tag_name
        logger.error(msg)
        return [jsonschema.ValidationError(msg, cause=e)]
    except FileNotFoundError as e:
        logger.warning('No schema document found for tag name %s : %s' % (tag_name, e))
    return []


def _validate_sort_key_fn(model_obj):
    """Produces a sort key validation function for the model object.

    :param model_obj: expects table, column, key, or fkey object
    :return: validation function
    """
    if hasattr(model_obj, 'table'):
        model_obj = model_obj.table
    if not hasattr(model_obj, 'column_definitions'):
        return _nop

    # collect column names
    _column_names = {c.name for c in model_obj.column_definitions}

    def _validation_func(validator, value, instance, schema):
        if not value:
            return
        # look for and validate column name
        col_name = instance if isinstance(instance, str) else instance.get('column') if isinstance(instance, dict) else None
        if col_name and col_name not in _column_names:
            raise jsonschema.ValidationError("'%s' not found in column definitions" % instance,
                                             validator=validator, validator_value=value,
                                             instance=instance, schema=schema)

    return _validation_func


def _validate_columns_fn(model_obj):
    """Produces a column validation function for the model object.

    The returned validation function will skip pseudo-columns.

    :param model_obj: table object
    :return: validation function
    """
    if not (hasattr(model_obj, 'column_definitions') and hasattr(model_obj, 'keys') and hasattr(model_obj, 'foreign_keys')):
        return _nop

    _column_names = {c.name for c in model_obj.column_definitions}
    _key_names = {(k.constraint_schema.name if k.constraint_schema else '', k.constraint_name) for k in model_obj.keys}
    _fkey_names = {(fk.constraint_schema.name if fk.constraint_schema else '', fk.constraint_name) for fk in model_obj.foreign_keys if fk is not None}
    _constraint_names = _key_names | _fkey_names

    # define a validation function for the model object
    def _validation_func(validator, value, instance, schema):
        if not value or not isinstance(instance, list):  # we expect the prior validate to ensure this is is a list
            return

        for item in instance:
            # validate simple column names
            if isinstance(item, str) and item not in _column_names:
                raise jsonschema.ValidationError("'%s' not found in column definitions" % item,
                                                 validator=validator, validator_value=value,
                                                 instance=instance, schema=schema)
            # validate simple key/fkey names
            elif isinstance(item, list) and len(item) == 2 and tuple(item) not in _constraint_names:
                raise jsonschema.ValidationError("'%s' not found in keys or foreign keys" % item,
                                                 validator=validator, validator_value=value,
                                                 instance=instance, schema=schema)
            # ignore other cases

    return _validation_func


def _validate_foreign_keys_fn(model_obj):
    """Produces a foreign keys validation function for the model object.

    The returned validation function will skip pseudo-columns.

    :param model_obj: table object
    :return: validation function
    """
    if not hasattr(model_obj, 'schema'):
        return _nop

    table = model_obj
    model = table.schema.model

    # define a validation function for the model object
    def _validation_func(validator, value, instance, schema):

        # we expect the prior validation to ensure this is a list
        if not value or not isinstance(instance, list):
            return

        # validate items
        for item in instance:
            if not (isinstance(item, list) and len(item) == 2):
                # if any item does not belong, simply break out, and stop validating
                break

            constraint_name = item
            try:
                fkey = model.fkey(constraint_name)
                if fkey.pk_table != table:
                    raise jsonschema.ValidationError("%s does not refer to '%s'" % (constraint_name, table.name))
            except KeyError as e:
                raise jsonschema.ValidationError("%s not found in foreign keys of model" % constraint_name, cause=e,
                                                 validator=validator, validator_value=value,
                                                 instance=instance, schema=schema)

    return _validation_func


def _validate_source_key_fn(model_obj):
    """Produces a source key validation function for the model object.

    :param model_obj: model object
    :return: validation function
    """
    sourcekeys = model_obj.annotations.get(tag.source_definitions, {}).get('sources', {})

    # define a validation function for the model object
    def _validation_func(validator, value, instance, schema):
        if value and isinstance(instance, str) and instance not in sourcekeys:
            raise jsonschema.ValidationError("'%s' not found in source definitions" % instance,
                                             validator=validator, validator_value=value, instance=instance, schema=schema)

    return _validation_func


def _validate_source_entry_fn(model_obj):
    """Produces a source entry validation function for the model object.

    :param model_obj: model object
    :return: validation function
    """
    if not (hasattr(model_obj, 'column_definitions') and hasattr(model_obj, 'schema')):
        return _nop

    _base_column_names = {c.name for c in model_obj.column_definitions}
    _model = model_obj.schema.model

    # define a validation function for the model object
    def _validation_func(validator, value, instance, schema):
        if not value:  # 'true' to indicate desire to validate model
            return

        # validate the simplest case of ..."source": "<column-name>"...
        if isinstance(instance, str) and instance not in _base_column_names:
            raise jsonschema.ValidationError("'%s' not found in column definitions" % instance,
                                             validator=validator, validator_value=value, instance=instance, schema=schema)

        # validate the fkey path case
        elif isinstance(instance, list):
            current_table = model_obj  # start the "current" table in the fkey path
            # iterate over the instance of the fkey path
            for item in instance:
                # validate that a column name belongs to the current table
                if isinstance(item, str):
                    if item not in {c.name for c in current_table.column_definitions}:
                        raise jsonschema.ValidationError(
                            "'%s' not found in column definitions of table %s" % (item, [current_table.schema.name, current_table.name]),
                            validator=validator, validator_value=value, instance=instance, schema=schema)

                # validate an inbound or outbound fkey in the path
                elif isinstance(item, dict) and any(isinstance(item[io], list) and len(item[io]) == 2 for io in ['inbound', 'outbound'] if io in item):
                    for direction, match_with_table, update_current_table in [
                        ('outbound',    'table',    'pk_table'),
                        ('inbound',     'pk_table', 'table')
                    ]:
                        if direction in item:
                            constraint_name = item[direction]
                            try:
                                fkey = _model.fkey(constraint_name)  # test if fkey exists in model
                                if getattr(fkey, match_with_table) != current_table:  # test if current table matches fkey table property
                                    raise jsonschema.ValidationError(
                                        "%s foreign key %s not associated with %s" % (direction, constraint_name, [current_table.schema.name, current_table.name]),
                                        validator=validator, validator_value=value, instance=instance, schema=schema)
                                current_table = getattr(fkey, update_current_table)  # update the "current" table
                            except KeyError as e:
                                # fkey not found in model
                                raise jsonschema.ValidationError("%s not found in model fkeys" % constraint_name, cause=e,
                                                                 validator=validator, validator_value=value,
                                                                 instance=instance, schema=schema)
                else:
                    break  # unrecognized source entry structure, break out and let schema validation take its course
        # and ignore anything unexpected

    return _validation_func
