# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Configuration data preparation without framework or process lifecycle imports."""
import os
import logging
from socket import getfqdn
from six import string_types
from sonicprobe import helpers
from sonicprobe.libs import network
from dwho.errors import DWhoConfigurationError
from dwho.configuration_schema import validate_configuration, validate_mapping

LOG = logging.getLogger('dwho.configuration')
MAX_BODY_SIZE = 8388608
MAX_WORKERS = 1
MAX_REQUESTS = 0
MAX_LIFE_TIME = 0
SUBDIR_LEVELS = 0
SUBDIR_CHARS = "abcdef0123456789"
CONFIG_IMPORT_SECTIONS = ('modules', 'plugins')

def get_server_id(conf = None):
    server_id = getfqdn()

    if isinstance(conf, dict) \
       and 'general' in conf \
       and conf['general'].get('server_id'):
        server_id = conf['general']['server_id']

    if not network.valid_domain(server_id):
        raise DWhoConfigurationError("Invalid server_id: %r" % server_id)

    return server_id

def parse_conf(conf, load_creds = False):
    return _parse_conf(conf, load_creds, globals())


def _parse_conf(conf, load_creds, defaults):
    validate_mapping(conf)
    # The legacy facade supplies its historical overridable defaults/helpers.
    if 'general' not in conf:
        raise DWhoConfigurationError("Missing 'general' section in configuration")

    validate_configuration(conf)

    if load_creds and 'credentials' in conf:
        conf['credentials'] = defaults['load_credentials'](conf['credentials'],
                                               conf.get('_config_directory'))

    conf['general']['server_id'] = defaults['get_server_id'](conf)

    if not conf['general'].get('max_body_size'):
        conf['general']['max_body_size'] = defaults['MAX_BODY_SIZE']

    conf['general']['max_workers'] = helpers.get_nb_workers(conf['general'].get('max_workers'),
                                                            xmin    = 1,
                                                            default = defaults['MAX_WORKERS'])

    if not conf['general'].get('max_requests'):
        conf['general']['max_requests'] = defaults['MAX_REQUESTS']

    if not conf['general'].get('max_life_time'):
        conf['general']['max_life_time'] = defaults['MAX_LIFE_TIME']

    if 'auth_basic_file' not in conf['general']:
        conf['general']['auth_basic'] = None
        conf['general']['auth_basic_file'] = None

    if 'subdir_levels' not in conf['general']:
        conf['general']['subdir_levels'] = defaults['SUBDIR_LEVELS']
    conf['general']['subdir_levels'] = int(conf['general']['subdir_levels'])

    if 'subdir_chars' not in conf['general']:
        conf['general']['subdir_chars'] = defaults['SUBDIR_CHARS']
    conf['general']['subdir_chars'] = set(str(conf['general']['subdir_chars']))

    if conf['general']['subdir_levels'] > 10:
        conf['general']['subdir_levels'] = 10
        defaults['LOG'].warning("option subdir_levels must not be greater than 10")

    if 'auth_basic' not in conf['general']:
        conf['general']['auth_basic'] = None

    if 'web_directories' in conf['general']:
        if isinstance(conf['general']['web_directories'], string_types):
            conf['general']['web_directories'] = [conf['general']['web_directories']]
        elif not isinstance(conf['general']['web_directories'], list):
            defaults['LOG'].error('Invalid %s type. (%s: %r, section: %r)',
                      'web_directories',
                      'web_directories',
                      conf['general']['web_directories'],
                      'general')
            conf['general']['web_directories'] = []
    else:
        conf['general']['web_directories'] = []

    return conf

def import_conf_files(name, conf):
    if not conf.get("import_%s" % name):
        return conf

    import_files = conf["import_%s" % name]

    if isinstance(import_files, string_types):
        import_files = [import_files]

    for import_file in import_files:
        conf[name] = helpers.merge(
            helpers.load_conf_yaml_file(
                import_file,
                conf['_config_directory']),
            conf.get(name) or {})

    return conf

def load_credentials(credentials, config_dir = None):
    if isinstance(credentials, string_types):
        return helpers.section_from_yaml_file(credentials, config_dir = config_dir)

    return credentials

def read_conf(xfile, parse_conf_func=None, load_creds=False, envvar=None,
              custom_file=None):
    """Read and normalize data; no signals, registries, watchers or threads.

    A custom parser replaces the default parser, as in the legacy loader.
    Inotify preparation belongs to the runtime, not to this function.
    """
    conf = read_conf_data(xfile, envvar=envvar, custom_file=custom_file)
    if parse_conf_func:
        conf = parse_conf_func(conf)
    else:
        conf = parse_conf(conf, load_creds)
    for name in CONFIG_IMPORT_SECTIONS:
        conf = import_conf_files(name, conf)
    return conf


def read_conf_data(xfile, envvar=None, custom_file=None):
    """Read YAML and optional overrides, before validation or section imports."""
    conf = {'_config_directory': None}

    if os.path.exists(xfile):
        with open(xfile, 'r') as f:
            conf = validate_mapping(helpers.load_yaml(f))

        config_directory = os.path.dirname(os.path.abspath(xfile))
        conf['_config_directory'] = config_directory

        if custom_file:
            conf = helpers.merge(
                helpers.load_conf_yaml_file(
                    custom_file,
                    config_directory),
                conf)
            conf['_config_directory'] = config_directory
    elif envvar and os.environ.get(envvar):
        conf = validate_mapping(helpers.load_yaml(os.environ[envvar]))
        conf['_config_directory'] = None

    return conf
