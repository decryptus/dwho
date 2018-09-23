# -*- coding: utf-8 -*-
"""dwho configuration"""

__author__  = "Adrien DELLE CAVE <adc@doowan.net>"
__license__ = """
    Copyright (C) 2015  doowan

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License along
    with this program; if not, write to the Free Software Foundation, Inc.,
    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA..
"""

import logging
import signal
import yaml

from dwho.classes.errors import DWhoConfigurationError
from dwho.classes.inoplugs import INOPLUGS
from dwho.classes.modules import MODULES
from dwho.classes.plugins import PLUGINS
from httpdis.httpdis import get_default_options
from logging.handlers import WatchedFileHandler
from sonicprobe.helpers import section_from_yaml_file
from sonicprobe.libs import keystore, network
from socket import getfqdn

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


def stop(signum, stack_frame):
    for thread in DWHO_THREADS:
        thread()

def get_server_id(conf):
    server_id = getfqdn()

    if 'general' in conf \
       and conf['general'].get('server_id'):
        server_id = conf['general']['server_id']

    if not network.valid_domain(server_id):
        raise DWhoConfigurationError("Invalid server_id: %r" % server_id)

    return server_id

def parse_conf(conf):
    global _INOTIFY

    if 'general' not in conf:
        raise DWhoConfigurationError("Missing 'general' section in configuration")

    conf['general']['server_id'] = get_server_id(conf)

    if not conf['general'].get('max_body_size'):
        conf['general']['max_body_size'] = MAX_BODY_SIZE

    if not conf['general'].get('max_workers'):
        conf['general']['max_workers'] = MAX_WORKERS

    if not conf['general'].get('max_requests'):
        conf['general']['max_requests'] = MAX_REQUESTS

    if not conf['general'].get('max_life_time'):
        conf['general']['max_life_time'] = MAX_LIFE_TIME

    if not conf['general'].has_key('auth_basic_file'):
        conf['general']['auth_basic'] = None
        conf['general']['auth_basic_file'] = None

    if not conf['general'].has_key('subdir_levels'):
        conf['general']['subdir_levels'] = SUBDIR_LEVELS
    conf['general']['subdir_levels'] = int(conf['general']['subdir_levels'])

    if not conf['general'].has_key('subdir_chars'):
        conf['general']['subdir_chars'] = SUBDIR_CHARS
    conf['general']['subdir_chars'] = set(str(conf['general']['subdir_chars']))

    if conf['general']['subdir_levels'] > 10:
        conf['general']['subdir_levels'] = 10
        LOG.warning("option subdir_levels must not be greather than 10")

    if not conf['general'].has_key('auth_basic'):
        conf['general']['auth_basic'] = None

    if conf['general'].has_key('web_directories'):
        if isinstance(conf['general']['web_directories'], basestring):
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

def load_conf(xfile, options = None, parse_conf_func = None):
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    with open(xfile, 'r') as f:
        conf = yaml.load(f)

    if parse_conf_func:
        conf = parse_conf_func(conf)
    else:
        conf = parse_conf(conf)

    for name, module in MODULES.iteritems():
        LOG.info("module init: %r", name)
        module.init(conf)

    for name, plugin in PLUGINS.iteritems():
        LOG.info("plugin init: %r", name)
        plugin.init(conf)

        if not plugin.enabled:
            continue

        LOG.info("plugin safe_init: %r", name)
        plugin.safe_init()
        DWHO_THREADS.append(plugin.at_stop)

    if _INOTIFY:
        _INOTIFY.init(conf)

        for name, inoplug in INOPLUGS.iteritems():
            LOG.info("inoplug init: %r", name)
            inoplug.init(conf)
            LOG.info("inoplug safe_init: %r", name)
            inoplug.safe_init()
            DWHO_THREADS.append(inoplug.at_stop)

    if not options or not isinstance(options, object):
        return conf

    for def_option in get_default_options().iterkeys():
        if getattr(options, def_option, None) is None \
           and def_option in conf['general']:
            setattr(options, def_option, conf['general'][def_option])

    setattr(options, 'configuration', conf)

    return options

def load_credentials(credentials, config_dir = None):
    if isinstance(credentials, basestring):
        return section_from_yaml_file(credentials, config_dir = config_dir)

    return credentials

def start_plugins():
    for name, plugin in PLUGINS.iteritems():
        if plugin.enabled and plugin.autostart:
            LOG.info("plugin at_start: %r", name)
            plugin.at_start()

def start_inoplugs():
    for name, inoplug in INOPLUGS.iteritems():
        if inoplug.enabled and inoplug.autostart:
            LOG.info("inoplug at_start: %r", name)
            inoplug.at_start()

def start_inotify():
    if not _INOTIFY:
        return

    start_inoplugs()
    _INOTIFY.start()

def init_logger(logfile, name):
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
