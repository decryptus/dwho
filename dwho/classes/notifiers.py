# -*- coding: utf-8 -*-
"""dwho notifiers"""

__author__  = "Adrien DELLE CAVE <adc@doowan.net>"
__license__ = """
    Copyright (C) 2018  doowan

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
import json
import logging
import os
import requests
import time
import yaml

from dwho.adapters.redis import DWhoAdapterRedis
from mako.template import Template
from socket import getfqdn
from sonicprobe.libs import urisup

LOG = logging.getLogger('dwho.notifiers')


class DWhoNotifiers(dict):
    def register(self, notifier):
        if not isinstance(notifier, DWhoNotifierBase):
            raise TypeError("Invalid Notifier class. (class: %r)" % notifier)

        if isinstance(notifier.SCHEME, basestring):
            schemes = [notifier.SCHEME]
        else:
            schemes = notifier.SCHEME

        if not isinstance(schemes, (list, tuple)):
            raise TypeError("Invalid Notifier SCHEME. (class: %r, scheme: %r)" % (notifier, schemes))

        for scheme in schemes:
            scheme = scheme.lower()
            if not dict.__contains__(self, scheme):
                dict.__setitem__(self, scheme, [])
            dict.__getitem__(self, scheme).append(notifier)

NOTIFIERS = DWhoNotifiers()


class DWhoPushNotifications(object):
    def __init__(self, server_id = None, config_path = None):
        self.notifications  = {}
        self.server_id      = server_id or getfqdn()

        if config_path:
            self.load(config_path)

    def load(self, config_path):
        if not config_path:
            LOG.warning("missing configuration directory")
            return

        if not os.path.isdir(config_path):
            LOG.error("invalid configuration directory: %r", config_path)
            return

        for xfile in os.listdir(config_path):
            xpath = os.path.join(config_path, xfile)
            if not xpath.endswith('.yml') or not os.path.isfile(xpath):
                continue

            f = None
            with open(xpath, 'r') as f:
                name = os.path.splitext(os.path.basename(xpath))[0]
                cfg  = yaml.load(f)

                self.notifications[name] = {'cfg': cfg,
                                            'tpl': None,
                                            'notifiers': []}

                if 'template' in cfg['general']:
                    with open(cfg['general']['template'], 'r') as t:
                        self.notifications[name]['tpl'] = t.read()

                uri_scheme = urisup.uri_help_split(cfg['general']['uri'])[0].lower()

                if uri_scheme in NOTIFIERS:
                    self.notifications[name]['notifiers'] = NOTIFIERS[uri_scheme]
                else:
                    raise NotImplementedError("unsupported notifiers: %r" % uri_scheme)

            if f:
                f.close()

    def reset(self):
        self.notifications = {}
        return self

    def __call__(self, xvars = {}):
        nvars                 = xvars.copy()
        nvars['_VARS_']       = xvars.copy()
        nvars['_SERVER_ID_']  = self.server_id
        nvars['_TIMESTAMP_']  = time.time()

        for name, notification in self.notifications.iteritems():
            if not notification['cfg']['general'].get('enabled', True):
                continue

            if notification['tpl']:
                tpl = json.loads(Template(notification['tpl'],
                                          imports = ['import json',
                                                     'from escapejson import escapejson']).render(**nvars))
            else:
                tpl = None

            cfg                   = notification['cfg'].copy()
            cfg['general']['uri'] = Template(cfg['general']['uri']).render(**nvars)

            for notifier in notification['notifiers']:
                notifier(name, cfg, tpl)


class DWhoNotifierBase(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractproperty
    def SCHEME(self):
        return


class DWhoNotifierHttp(DWhoNotifierBase):
    SCHEME = ('http', 'https')

    def __call__(self, name, cfg, tpl = None):
        (headers, payload) = ({}, {})

        if tpl:
            if 'headers' in tpl:
                headers = tpl['headers']

            if 'payload' in tpl:
                payload = tpl['payload']

        try:
            r = requests.post(cfg['general']['uri'],
                              headers = headers,
                              data    = payload)

            if 200 <= r.status_code < 300:
                LOG.info("notification pushed: %r", name)
                return True

            LOG.error("unable to push notification: %r: %r", name, r.text)
        except Exception, e:
            LOG.error("unable to push notification %r: %r", name, e)


class DWhoNotifierRedis(DWhoNotifierBase):
    SCHEME = ('redis',)

    def __call__(self, name, cfg, tpl):
        config = {'general':
                   {'redis':
                     {'notifier': cfg['general'].get('options') or {}}}}
        config['general']['redis']['notifier']['url'] = cfg['general']['uri']

        if not tpl:
            LOG.error("missing redis template for %r", name)
            return

        try:
            adapter_redis = DWhoAdapterRedis(config, prefix = 'notifier')
            adapter_redis.set_key(tpl['key'], json.dumps(tpl['value']))
        except Exception, e:
            LOG.error("unable to push notification %r: %r", name, e)
        else:
            LOG.info("notification pushed: %r", name)


if __name__ != "__main__":
    def _start():
        NOTIFIERS.register(DWhoNotifierHttp())
        NOTIFIERS.register(DWhoNotifierRedis())
    _start()
