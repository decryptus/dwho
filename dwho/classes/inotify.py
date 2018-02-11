# -*- coding: utf-8 -*-
"""dwho inotify"""

__author__  = "Adrien DELLE CAVE <adc@doowan.net>"
__license__ = """
    Copyright (C) 2017  doowan

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

import abc
import logging
import os
import pyinotify
import Queue

from dwho.classes.errors import DWhoConfigurationError, DWhoInotifyError
from dwho.classes.inoplugs import CACHE_EXPIRE, INOPLUGS, LOCK_TIMEOUT
from sonicprobe.libs.workerpool import WorkerPool
from threading import Thread

LOG             = logging.getLogger('dwho.inotify')

DWHO_INOQ       = Queue.Queue()

MODE_ADD        = 'MODE_ADD'
MODE_REM        = 'MODE_REM'

MAX_WORKERS     = 5

DEFAULT_CONFIG  = {'plugins':   dict(zip(INOPLUGS.keys(),
                                         [False] * len(INOPLUGS.keys()))),
                   'events':    ['create',
                                 'close_write',
                                 'move_self',
                                 'moved_to',
                                 'moved_from']}


class DWhoInotifyCfgPath(object):
    def __init__(self,
                 path,
                 event_mask     = 0,
                 plugins        = None,
                 do_glob        = False,
                 exclude_filter = None):
        self.path           = path
        self.event_mask     = event_mask
        self.plugins        = plugins
        self.do_glob        = do_glob
        self.exclude_filter = exclude_filter


class DWhoInotifyConfig(object):
    def __call__(self, notifier, conf):
        if not conf.has_key('plugins'):
            conf['plugins'] = DEFAULT_CONFIG['plugins'].copy()

        if not conf.has_key('events'):
            conf['events'] = list(DEFAULT_CONFIG['events'])

        if conf.has_key('exclude_files'):
            if isinstance(conf['exclude_files'], basestring):
                conf['exclude_files'] = [conf['exclude_files']]
            elif not isinstance(conf['exclude_files'], list):
                LOG.error('Invalid %s type. (%s: %r, section: %r)',
                          'exclude_files',
                          'exclude_files',
                          conf['exclude_files'],
                          'inotify')
                conf['exclude_files'] = []
        else:
            conf['exclude_files'] = []

        if not conf.has_key('paths') or not isinstance(conf['paths'], dict):
            raise DWhoConfigurationError("Missing paths configuration")

        for path, value in conf['paths'].iteritems():
            if not value.has_key('plugins'):
                value['plugins'] = conf['plugins'].copy()

            value['event_masks']    = 0

            if not value.has_key('events'):
                value['events'] = list(conf['events'])
            else:
                for event in value['events']:
                    if not event.startswith('-'):
                        continue
                    event = event[1:]
                    if event in value['events']:
                        value['events'].remove(event)

            if not value['events']:
                raise DWhoConfigurationError("Invalid configured events. (events: %r, path: %r)"
                                             % (value['events'], path))
            else:
                for event in value['events']:
                    if not self.valid_event(event):
                        raise DWhoConfigurationError("Invalid configured event: %r. (path: %r)"
                                                     % (event, path))
                    value['event_masks'] |= DWhoInotify.get_flag_value(event)

            if not value.has_key('exclude_files'):
                value['exclude_files'] = list(conf['exclude_files'])
            else:
                if isinstance(value['exclude_files'], basestring):
                    value['exclude_files'] = [value['exclude_files']]
                elif not isinstance(value['exclude_files'], list):
                    raise DWhoConfigurationError("Invalid exclude_files type. (exclude_files: %r, path: %r)"
                                                 % (value['exclude_files'], path))

                for exclude_file in value['exclude_files']:
                    if not exclude_file.startswith('-'):
                        continue
                    exclude_file = exclude_file[1:]
                    if exclude_file in value['exclude_files']:
                        value['exclude_files'].remove(exclude_file)

            value['exclude_patterns']   = set()

            if value['exclude_files']:
                for x in value['exclude_files']:
                    pattern = load_patterns_from_file(x)
                    if not pattern:
                        raise DWhoConfigurationError("Unable to load exclude patterns from %r. (path: %r)"
                                                     % (x, path))

                    value['exclude_patterns'].update(pattern)

            if value['exclude_patterns']:
                value['exclude_patterns'] = pyinotify.ExcludeFilter(list(value['exclude_patterns']))
            else:
                value['exclude_patterns'] = None

        for path, value in conf['paths'].iteritems():
            plugins     = []
            if value['plugins']:
                for plugin, options in value['plugins'].iteritems():
                    if not options:
                        continue
                    if INOPLUGS.has_key(plugin):
                        plugins.append(INOPLUGS[plugin])

            notifier.add(DWhoInotifyCfgPath(path,
                                            value['event_masks'],
                                            plugins,
                                            value.get('glob'),
                                            value['exclude_patterns']))
        return conf

    @staticmethod
    def valid_event(event):
        return event in DEFAULT_CONFIG['events']


class DWhoInotify(Thread):
    def __init__(self):
        self.config      = None
        self.killed      = False
        self.cfg_paths   = {}
        self.notifier    = None
        self.wm          = None
        self.workerpool  = None

        Thread.__init__(self)

    def init(self, config):
        self.config     = config
        self.workerpool = WorkerPool(None,
                                     config['inotify'].get('max_workers', MAX_WORKERS),
                                     config['inotify'].get('worker_lifetime'))

        return self

    @staticmethod
    def add(cfg_path):
        DWHO_INOQ.put((MODE_ADD, cfg_path))

    @staticmethod
    def rem(cfg_path):
        DWHO_INOQ.put((MODE_REM, cfg_path))

    @staticmethod
    def get_flag_value(name):
        if pyinotify.EventsCodes.ALL_FLAGS.has_key(name):
            return pyinotify.EventsCodes.ALL_FLAGS.get(name)

        if not isinstance(name, basestring):
            return

        uname   = name.upper()
        if pyinotify.EventsCodes.ALL_FLAGS.has_key(uname):
            return pyinotify.EventsCodes.ALL_FLAGS.get(uname)

        uname   = "IN_%s" % uname
        if pyinotify.EventsCodes.ALL_FLAGS.has_key(uname):
            return pyinotify.EventsCodes.ALL_FLAGS.get(uname)

    @staticmethod
    def valid_flag(name):
        return DWhoInotify.get_flag_value(name) is not None

    def get_cfg_path(self, path):
        if self.cfg_paths.has_key(path):
            LOG.debug("path: %r, wd_path: %r, common: %r",
                      path,
                      path.rstrip(os.sep),
                      os.path.commonprefix([path, path]))
            return self.cfg_paths[path]

        try:
            cfg_paths = self.cfg_paths.copy()
            for wd_path in cfg_paths.iterkeys():
                if os.path.commonprefix([path, wd_path]) == wd_path.rstrip(os.sep):
                    LOG.debug("path: %r, wd_path: %r, common: %r",
                              path,
                              wd_path.rstrip(os.sep),
                              os.path.commonprefix([path, wd_path]))
                    return self.cfg_paths[wd_path]
        finally:
            cfg_paths = None

    def __add_watch(self, cfg_path):
        LOG.debug("Add watch. (path: %r, mask: %r, plugins: %r, glob: %r)",
                  cfg_path.path,
                  cfg_path.event_mask,
                  cfg_path.plugins,
                  cfg_path.do_glob)

        try:
            wdd = self.wm.add_watch(cfg_path.path,
                                    cfg_path.event_mask,
                                    rec             = True,
                                    auto_add        = True,
                                    quiet           = False,
                                    do_glob         = cfg_path.do_glob,
                                    exclude_filter  = cfg_path.exclude_filter)

            for wpath, wcode in wdd.iteritems():
                if wcode < 0:
                    LOG.error("Unable to monitor. (path: %r, code: %r)", wpath, wcode)
                else:
                    self.cfg_paths[wpath] = cfg_path
        except pyinotify.WatchManagerError, e:
            LOG.exception("Unable to monitor. (path: %r, reason: %r)", path, e)
        finally:
            wdd = None

    def __rem_watch(self, cfg_path):
        if not self.cfg_paths.has_key(cfg_path.path):
            return

        LOG.debug("Remove watch. (path: %r, mask: %r, plugins: %r, glob: %r)",
                  cfg_path.path,
                  cfg_path.event_mask,
                  cfg_path.plugins,
                  cfg_path.do_glob)

        try:
            self.wm.rm_watch(cfg_path.path, rec = True, quiet = False)
        except pyinotify.WatchManagerError, e:
            LOG.exception("Unable to unmonitor. (path: %r, reason: %r)", cfg_path.path, e)
        else:
            del self.cfg_paths[cfg_path.path]

    def run(self):
        self.wm         = pyinotify.WatchManager()
        self.notifier   = pyinotify.ThreadedNotifier(self.wm,
                                                     DWhoInotifyEventHandler(**{'dw_inotify': self}))
        self.notifier.start()

        while not self.killed:
            try:
                (mode, cfg_path) = DWHO_INOQ.get(True, 0.5)
                if mode == MODE_ADD:
                    self.__add_watch(cfg_path)
                elif mode == MODE_REM:
                    self.__rem_watch(cfg_path)
                else:
                    raise DWhoInotifyError("Invalid mode: %r" % mode)
            except Queue.Empty:
                pass

        self.notifier.stop()

    def stop(self):
        self.killed = True
        self.workerpool.killall(0)


class DWhoInotifyEventHandler(pyinotify.ProcessEvent):
    def my_init(self, dw_inotify):
        self.dw_inotify = dw_inotify
        self.workerpool = dw_inotify.workerpool

    def call_plugins(self, cfg_path, event):
        if not cfg_path.plugins:
            LOG.warning("No plugin enabled")
            return

        if not hasattr(event, 'pathname'):
            LOG.warning("Missing pathname in Event. (event: %r)", event)
            return

        filepath = event.pathname

        try:
            os.path.isfile(filepath)
        except UnicodeEncodeError:
            LOG.exception("Encoding error file: %r", filepath)
            return

        if cfg_path.exclude_filter and cfg_path.exclude_filter(filepath):
            LOG.debug("Exclude file from scan. (filepath: %r)", filepath)
            return

        self.workerpool.run(DWhoInotifyPlugs(self.dw_inotify.config, cfg_path, event, filepath).run)

    def process_IN_CREATE(self, event):
        cfg_path  = self.dw_inotify.get_cfg_path(event.path)
        if cfg_path:
            self.call_plugins(cfg_path, event)

        LOG.debug("DWhoInotifyEvent reports that an CREATE event has occurred. (event: %r)", event)

    def process_IN_CLOSE_WRITE(self, event):
        cfg_path  = self.dw_inotify.get_cfg_path(event.path)
        if cfg_path:
            self.call_plugins(cfg_path, event)

        LOG.debug("DWhoInotifyEvent reports that an CLOSE_WRITE event has occurred. (event: %r)", event)

    def process_IN_DELETE(self, event):
        cfg_path  = self.dw_inotify.get_cfg_path(event.path)
        if cfg_path:
            self.call_plugins(cfg_path, event)

        LOG.debug("DWhoInotifyEvent reports that a DELETE event has occurred. (event: %r)", event)

    def process_IN_MODIFY(self, event):
        cfg_path  = self.dw_inotify.get_cfg_path(event.path)
        if cfg_path:
            self.call_plugins(cfg_path, event)

        LOG.debug("DWhoInotifyEvent reports that a MODIFY event has occurred. (event: %r)", event)

    def process_IN_ATTRIB(self, event):
        cfg_path  = self.dw_inotify.get_cfg_path(event.path)
        if cfg_path:
            self.call_plugins(cfg_path, event)

        LOG.debug("DWhoInotifyEvent reports that a ATTRIB event has occurred. (event: %r)", event)

    def process_IN_MOVE_SELF(self, event):
        cfg_path  = self.dw_inotify.get_cfg_path(event.path)
        if cfg_path:
            self.call_plugins(cfg_path, event)

        LOG.debug("DWhoInotifyEvent reports that a MOVE_SELF event has occurred. (event: %r)", event)

    def process_IN_MOVED_TO(self, event):
        cfg_path  = self.dw_inotify.get_cfg_path(event.path)
        if cfg_path:
            self.call_plugins(cfg_path, event)

        LOG.debug("DWhoInotifyEvent reports that a MOVED_TO event has occurred. (event: %r)", event)

    def process_IN_MOVED_FROM(self, event):
        cfg_path  = self.dw_inotify.get_cfg_path(event.path)
        if cfg_path:
            self.call_plugins(cfg_path, event)

        LOG.debug("DWhoInotifyEvent reports that a MOVED_FROM event has occurred. (event: %r)", event)

    def process_IN_Q_OVERFLOW(self, event):
        LOG.debug("DWhoInotifyEvent reports that a Q_OVERFLOW event has occurred. (event: %r)", event)

    def process_default(self, event):
        LOG.debug("DWhoInotifyEvent reports that an unsupported event has occurred. (event: %r)", event)


class DWhoInotifyPlugs(Thread):
    def __init__(self, config, cfg_path, event, filepath):
        Thread.__init__(self)

        self.cache_expire   = config['inotify'].get('cache_expire', CACHE_EXPIRE)
        self.config         = config
        self.cfg_path       = cfg_path
        self.event          = event
        self.filepath       = filepath
        self.timeout        = config['inotify'].get('lock_timeout', LOCK_TIMEOUT)
        self.server_id      = config['general']['server_id']

    def run(self):
        try:
            for plugin in self.cfg_path.plugins:
                LOG.debug("Starting plugin %s. (filename: %r, thread: %r)",
                          plugin.PLUGIN_NAME,
                          self.filepath,
                          self.name)

                plugin(self.cfg_path, self.event, self.filepath)

                LOG.debug("Stopping plugin %s. (filename: %r, thread: %r)",
                          plugin.PLUGIN_NAME,
                          self.filepath,
                          self.name)
        except Exception, e:
            LOG.exception("Error during plugin. (error: %r, filename: %r)",
                          e,
                          self.filepath)

    def __call__(self):
        return self.start()
