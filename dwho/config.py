# -*- coding: utf-8 -*-
# Copyright (C) 2015-2019 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""dwho.classes.config"""

import os
import signal

import logging
from logging.handlers import WatchedFileHandler

from socket import getfqdn

from six import iterkeys, iteritems, string_types
try:
    from six.moves import cStringIO as StringIO
except ImportError:
    from six import StringIO

from httpdis.httpdis import get_default_options
from sonicprobe import helpers
from sonicprobe.libs import keystore, network
from dwho.classes.errors import DWhoConfigurationError
from dwho.classes.inoplugs import INOPLUGS
from dwho.classes.modules import MODULES
from dwho.classes.plugins import PLUGINS

LOG             = logging.getLogger('dwho.config')

MAX_BODY_SIZE   = 8388608
MAX_WORKERS     = 1
MAX_REQUESTS    = 0
MAX_LIFE_TIME   = 0
SUBDIR_LEVELS   = 0
SUBDIR_CHARS    = "abcdef0123456789"

DWHO_SHARED     = keystore.Keystore()
DWHO_THREADS    = []
_INOTIFY        = None
_SOFTNAME       = ""
_SOFTVER        = ""


def stop(signum, stack_frame): # pylint: disable=unused-argument
    for t in DWHO_THREADS:
        t()

def set_softname(name):
    global _SOFTNAME

    if not _SOFTNAME and helpers.has_len(name):
        _SOFTNAME = name

def get_softname():
    return _SOFTNAME

def set_softver(version):
    global _SOFTVER

    if not _SOFTVER and helpers.has_len(version):
        _SOFTVER = version

def get_softver():
    return _SOFTVER

def get_server_id(conf = None):
    server_id = getfqdn()

    if isinstance(conf, dict) \
       and 'general' in conf \
       and conf['general'].get('server_id'):
        server_id = conf['general']['server_id']

    if not network.valid_domain(server_id):
        raise DWhoConfigurationError("Invalid server_id: %r" % server_id)

    return server_id

def get_inotify_instance():
    return _INOTIFY

def parse_conf(conf, load_creds = False):
    global _INOTIFY

    if 'general' not in conf:
        raise DWhoConfigurationError("Missing 'general' section in configuration")

    if load_creds and 'credentials' in conf:
        conf['credentials'] = load_credentials(conf['credentials'],
                                               conf.get('_config_directory'))

    conf['general']['server_id'] = get_server_id(conf)

    if not conf['general'].get('max_body_size'):
        conf['general']['max_body_size'] = MAX_BODY_SIZE

    conf['general']['max_workers'] = helpers.get_nb_workers(conf['general'].get('max_workers'),
                                                            xmin    = 1,
                                                            default = MAX_WORKERS)

    if not conf['general'].get('max_requests'):
        conf['general']['max_requests'] = MAX_REQUESTS

    if not conf['general'].get('max_life_time'):
        conf['general']['max_life_time'] = MAX_LIFE_TIME

    if 'auth_basic_file' not in conf['general']:
        conf['general']['auth_basic'] = None
        conf['general']['auth_basic_file'] = None

    if 'subdir_levels' not in conf['general']:
        conf['general']['subdir_levels'] = SUBDIR_LEVELS
    conf['general']['subdir_levels'] = int(conf['general']['subdir_levels'])

    if 'subdir_chars' not in conf['general']:
        conf['general']['subdir_chars'] = SUBDIR_CHARS
    conf['general']['subdir_chars'] = set(str(conf['general']['subdir_chars']))

    if conf['general']['subdir_levels'] > 10:
        conf['general']['subdir_levels'] = 10
        LOG.warning("option subdir_levels must not be greater than 10")

    if 'auth_basic' not in conf['general']:
        conf['general']['auth_basic'] = None

    if 'web_directories' in conf['general']:
        if isinstance(conf['general']['web_directories'], string_types):
            conf['general']['web_directories'] = [conf['general']['web_directories']]
        elif not isinstance(conf['general']['web_directories'], list):
            LOG.error('Invalid %s type. (%s: %r, section: %r)',
                      'web_directories',
                      'web_directories',
                      conf['general']['web_directories'],
                      'general')
            conf['general']['web_directories'] = []
    else:
        conf['general']['web_directories'] = []

    if 'inotify' in conf:
        from dwho.classes import inotify

        _INOTIFY = inotify.DWhoInotify()
        DWHO_THREADS.append(_INOTIFY.stop)
        conf['inotify'] = inotify.DWhoInotifyConfig()(_INOTIFY, conf['inotify'])

    return conf

def load_conf(xfile, options = None, parse_conf_func = None, load_creds = False, envvar = None, custom_file = None):
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    conf = {'_config_directory': None}

    if os.path.exists(xfile):
        with open(xfile, 'r') as f:
            conf = helpers.load_yaml(f)

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
        c = StringIO(os.environ[envvar])
        conf = helpers.load_yaml(c.getvalue())
        c.close()
        conf['_config_directory'] = None

    if parse_conf_func:
        conf = parse_conf_func(conf)
    else:
        conf = parse_conf(conf, load_creds)

    for name, module in iteritems(MODULES):
        LOG.info("module init: %r", name)
        module.init(conf)

    for name, plugin in iteritems(PLUGINS):
        LOG.info("plugin init: %r", name)
        plugin.init(conf)

        if not plugin.enabled:
            continue

        LOG.info("plugin safe_init: %r", name)
        plugin.safe_init()
        DWHO_THREADS.append(plugin.at_stop)

    if _INOTIFY:
        _INOTIFY.init(conf)

        for name, inoplug in iteritems(INOPLUGS):
            LOG.info("inoplug init: %r", name)
            inoplug.init(conf)
            LOG.info("inoplug safe_init: %r", name)
            inoplug.safe_init()
            DWHO_THREADS.append(inoplug.at_stop)

    if not options or not isinstance(options, object):
        return conf

    for def_option in iterkeys(get_default_options()):
        if getattr(options, def_option, None) is None \
           and def_option in conf['general']:
            setattr(options, def_option, conf['general'][def_option])

    setattr(options, 'configuration', conf)

    return options

def load_credentials(credentials, config_dir = None):
    if isinstance(credentials, string_types):
        return helpers.section_from_yaml_file(credentials, config_dir = config_dir)

    return credentials

def start_plugins():
    for name, plugin in iteritems(PLUGINS):
        if plugin.enabled and plugin.autostart:
            LOG.info("plugin at_start: %r", name)
            plugin.at_start()

def start_inoplugs():
    for name, inoplug in iteritems(INOPLUGS):
        if inoplug.enabled and inoplug.autostart:
            LOG.info("inoplug at_start: %r", name)
            inoplug.at_start()

def start_inotify():
    if not _INOTIFY:
        return

    start_inoplugs()
    _INOTIFY.start()

def make_piddir(pidfile, uid, gid):
    piddir = os.path.dirname(pidfile)
    if piddir and not os.path.exists(piddir):
        helpers.make_dirs(piddir)
        os.chown(piddir, uid, gid)

def make_logdir(logfile, uid, gid):
    logdir = os.path.dirname(logfile)
    if logdir and not os.path.exists(logdir):
        helpers.make_dirs(logdir)
        os.chown(logdir, uid, gid)

def init_logger(logfile, name = None): # pylint: disable=unused-argument
    xformat     = "%(levelname)s:%(asctime)-15s %(name)s[%(process)d][%(threadName)s]: %(message)s"
    datefmt     = '%Y-%m-%d %H:%M:%S'
    logging.basicConfig(level   = logging.DEBUG,
                        format  = xformat,
                        datefmt = datefmt)
    filehandler = WatchedFileHandler(logfile)
    filehandler.setFormatter(logging.Formatter(xformat,
                                               datefmt=datefmt))
    root_logger = logging.getLogger('')
    root_logger.addHandler(filehandler)

    return root_logger
