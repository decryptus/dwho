"""XYS configuration structure checks, without loading or initializing services."""
from sonicprobe.libs import xys
from dwho.errors import DWhoConfigurationError


xys.add_callback('dwho.config.mapping', lambda value: isinstance(value, dict))
MAPPING = '!~~callback(dwho.config.mapping) null'
MAPPING_SCHEMA = xys.load(MAPPING)


def validate_fields(data, schema):
    # Unknown fields belong to extensions. Never use a wildcard that could consume
    # known optional fields before their XYS validators run.
    if not isinstance(data, dict) or not xys.validate(
            {key: value for key, value in data.items() if key in schema}, schema):
        raise DWhoConfigurationError('Invalid configuration structure')
    return data


def validate_mapping(data):
    if not xys.validate(data, MAPPING_SCHEMA):
        raise DWhoConfigurationError('Invalid configuration mapping')
    return data


CONFIG_SCHEMA = xys.load('''
general: %s
modules*: %s
plugins*: %s
''' % (MAPPING, MAPPING, MAPPING))


def validate_configuration(conf):
    validate_fields(conf, CONFIG_SCHEMA)
    return conf
