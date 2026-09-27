# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit application lifecycle, independent of HTTP and command interfaces."""
import copy
import logging
import threading

from sonicprobe.libs.keystore import Keystore

LOG = logging.getLogger('dwho.runtime')


class DWhoRuntime(object):
    """One-shot runtime. Supply fresh extension instances and a route registrar.

    Initialization/startup are launcher operations, serialized by the caller.
    HTTP transport startup/shutdown and signal ownership remain with the launcher.
    """
    def __init__(self, modules=None, plugins=None, inoplugs=None,
                 route_registrar=None, inotify_factory=None,
                 inotify_config_factory=None):
        self.modules = dict(modules or {})
        self.plugins = dict(plugins or {})
        self.inoplugs = dict(inoplugs or {})
        self.route_registrar = route_registrar
        self.inotify_factory = inotify_factory
        self.inotify_config_factory = inotify_config_factory
        self.shared = Keystore()
        self.configuration = None
        self.inotify = None
        self._callbacks = []
        self._stop_lock = threading.Lock()
        self.state = 'new'

    def initialize(self, configuration):
        if self.state != 'new':
            raise RuntimeError('Runtime initialization is one-shot')
        extensions = list(self.modules.values()) + list(self.plugins.values())
        extensions += list(self.inoplugs.values())
        if self.modules and not callable(self.route_registrar):
            raise ValueError('Modules require an explicit route registrar')
        for extension in extensions:
            if getattr(extension, '_dwho_runtime', None) is not None \
               or getattr(extension, 'initialized', False):
                raise ValueError('Each runtime requires fresh extension instances')
        # Copy data before invoking user code; contexts never share normalized data.
        self.configuration = copy.deepcopy(configuration)
        self.state = 'initializing'
        for extension in extensions:
            extension._dwho_runtime = self
        try:
            if 'inotify' in self.configuration:
                factory = self.inotify_factory
                config_factory = self.inotify_config_factory
                if factory is None or config_factory is None:
                    from dwho.classes.inotify import DWhoInotifyContext, DWhoInotifyConfig
                    factory = factory or DWhoInotifyContext
                    config_factory = config_factory or DWhoInotifyConfig
                self.inotify = factory()
                self._callbacks.append(self.inotify.stop)
                self.configuration['inotify'] = config_factory(plugins=self.inoplugs)(
                    self.inotify, self.configuration['inotify'])
            for module in self.modules.values():
                module.route_registrar = self.route_registrar
                module.init(self.configuration)
            for plugin in self.plugins.values():
                plugin.init(self.configuration)
                if plugin.enabled:
                    self._callbacks.append(plugin.at_stop)
                    plugin.safe_init()
            if self.inotify is not None:
                self.inotify.init(self.configuration)
                for plugin in self.inoplugs.values():
                    plugin.init(self.configuration)
                    self._callbacks.append(plugin.at_stop)
                    plugin.safe_init()
            self.state = 'ready'
        except BaseException:
            self._cleanup_after_failure()
            raise
        return self

    def start(self):
        if self.state != 'ready':
            raise RuntimeError('Runtime must be ready before start')
        self.state = 'starting'
        try:
            for plugin in self.plugins.values():
                if plugin.enabled and plugin.autostart:
                    plugin.at_start()
            if self.inotify is not None:
                for plugin in self.inoplugs.values():
                    if plugin.enabled and plugin.autostart:
                        plugin.at_start()
                self.inotify.start()
            self.state = 'running'
        except BaseException:
            self._cleanup_after_failure()
            raise
        return self

    def _cleanup_after_failure(self):
        try:
            self.stop()
        except BaseException:
            LOG.exception('Runtime cleanup failed')

    def stop(self):
        # Run every registered cleanup once, even when a callback fails.
        with self._stop_lock:
            if self.state == 'stopped':
                return
            self.state = 'stopped'
            callbacks = self._callbacks
            self._callbacks = []
        first_error = None
        for callback in callbacks:
            try:
                callback()
            except BaseException as error:
                if first_error is None:
                    first_error = error
                LOG.exception('Runtime stop callback failed')
        if first_error is not None:
            raise first_error
