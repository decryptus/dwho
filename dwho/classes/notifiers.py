# -*- coding: utf-8 -*-
# Copyright (C) 2015-2019 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""dwho.classes.notifiers"""

import abc
import copy
import json
import logging
import os
import subprocess
import threading
import time
import uuid

from datetime import datetime

from socket import getfqdn
from mako.template import Template

from dotenv.main import dotenv_values

from sonicprobe import helpers
from sonicprobe.libs import urisup
from sonicprobe.libs.workerpool import WorkerPool

import requests
import six

from dwho.adapters.redis import DWhoAdapterRedis
from dwho.config import get_softname, get_softver
from dwho.classes.abstract import DWhoAbstractHelper


LOG = logging.getLogger('dwho.notifiers')

HTTP_ALLOWED_METHODS = ('delete', 'head', 'get', 'patch', 'post', 'put')
DEFAULT_TIMEOUT      = 30


class DWhoNotifiers(dict):
    def register(self, notifier):
        if not isinstance(notifier, DWhoNotifierBase):
            raise TypeError("Invalid Notifier class. (class: %r)" % notifier)

        if isinstance(notifier.SCHEME, six.string_types):
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


class DWhoPushNotifications(object): # pylint: disable=useless-object-inheritance
    def __init__(self, server_id = None, config_path = None):
        self.notifications  = {}
        self.server_id      = server_id or getfqdn()
        self.workerpool     = None
        self._lock          = threading.Lock()

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
                cfg  = helpers.load_yaml(f)

                self.notifications[name] = {'cfg': cfg,
                                            'tpl': None,
                                            'notifiers': []}

                if cfg['general'].get('template') and os.path.isfile(cfg['general']['template']):
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

    def _run(self, xvars = None):
        if not xvars:
            xvars = {}

        nvars                = copy.deepcopy(xvars)
        nvars['_ENV_']       = copy.deepcopy(os.environ)
        nvars['_GMTIME_']    = datetime.utcnow()
        nvars['_HOSTNAME_']  = getfqdn()
        nvars['_SERVER_ID_'] = self.server_id
        nvars['_SOFTNAME_']  = get_softname()
        nvars['_SOFTVER_']   = get_softver()
        nvars['_TIME_']      = datetime.now()
        nvars['_TIMESTAMP_'] = time.time()
        nvars['_UUID_']      = "%s" % uuid.uuid4()
        nvars['_VARS_']      = copy.deepcopy(xvars)

        if not self.workerpool:
            self.workerpool = WorkerPool(max_workers = 1,
                                         name = 'notifiers')

        for name, notification in six.iteritems(self.notifications):
            if not notification['cfg']['general'].get('enabled', True):
                continue

            if notification['tpl']:
                tpl = json.loads(Template(notification['tpl'],
                                          imports = ['import json',
                                                     'from escapejson import escapejson',
                                                     'from os import environ as ENV']).render(**nvars))
            else:
                tpl = None

            cfg                   = notification['cfg'].copy()
            cfg['general']['uri'] = Template(cfg['general']['uri']).render(**nvars)
            uri                   = urisup.uri_help_split(cfg['general']['uri'])

            for notifier in notification['notifiers']:
                if cfg['general'].get('async'):
                    self.workerpool.run_args(notifier,
                                             _name_ = "notifier:%s" % name,
                                             name   = name,
                                             cfg    = cfg,
                                             uri    = uri,
                                             nvars  = nvars,
                                             tpl    = tpl)
                else:
                    notifier(name, cfg, uri, nvars, tpl)

        while self.workerpool:
            if self.workerpool.killable():
                self.workerpool.killall(0)
                self.workerpool = None
            time.sleep(0.5)

    def __call__(self, xvars = None):
        with self._lock:
            try:
                self._run(xvars)
            except Exception as e:
                LOG.exception(e)


class DWhoNotifierBase(DWhoAbstractHelper): # pylint: disable=useless-object-inheritance
    __metaclass__ = abc.ABCMeta

    @abc.abstractproperty
    def SCHEME(self):
        return


class DWhoNotifierHttp(DWhoNotifierBase):
    SCHEME = ('http', 'https')

    def __call__(self, name, cfg, uri, nvars, tpl = None):
        (method, auth, headers, payload) = ('post', None, {}, {})

        if not isinstance(tpl, dict):
            tpl = {}

        timeout = tpl.get('timeout', cfg.get('timeout', DEFAULT_TIMEOUT))
        verify  = tpl.get('verify', cfg.get('verify'))

        if tpl.get('method'):
            if tpl['method'].lower() in HTTP_ALLOWED_METHODS:
                method = tpl['method'].lower()
            else:
                raise ValueError("invalid HTTP method: %r" % tpl['method'])

        if isinstance(tpl.get('auth'), dict):
            auth = tpl['auth']

        if 'headers' in tpl:
            headers = tpl['headers']

        if 'payload' in tpl:
            payload = tpl['payload']

        try:
            r = getattr(requests, method)(cfg['general']['uri'],
                                          auth    = auth,
                                          headers = headers,
                                          data    = payload,
                                          timeout = timeout,
                                          verify  = verify)

            if 200 <= r.status_code < 300:
                LOG.info("notification pushed: %r", name)
                return True

            LOG.error("unable to push notification: %r: %r", name, r.text)
        except Exception as e:
            LOG.error("unable to push notification %r: %r", name, e)

        return None


class DWhoNotifierRedis(DWhoNotifierBase):
    SCHEME = ('redis',)

    def __call__(self, name, cfg, uri, nvars, tpl):
        config = {'general':
                  {'redis':
                   {'notifier': cfg['general'].get('options') or {}}}}
        config['general']['redis']['notifier']['url'] = cfg['general']['uri']

        if not tpl or not isinstance(tpl, dict):
            LOG.error("missing redis template for %r", name)
            return

        try:
            adapter_redis = DWhoAdapterRedis(config, prefix = 'notifier')
            adapter_redis.set_key(tpl['key'], json.dumps(tpl['value']))
        except Exception as e:
            LOG.error("unable to push notification %r: %r", name, e)
        else:
            LOG.info("notification pushed: %r", name)


class DWhoNotifierSubprocess(DWhoNotifierBase):
    SCHEME = ('subproc',)

    @staticmethod
    def _set_default_env(env, xvars):
        env.update({'DWHO_NOTIFIER':           'true',
                    'DWHO_NOTIFIER_HOSTNAME':  "%s" % getfqdn(),
                    'DWHO_NOTIFIER_GMTIME':    "%s" % xvars['_GMTIME_'],
                    'DWHO_NOTIFIER_TIME':      "%s" % xvars['_TIME_'],
                    'DWHO_NOTIFIER_TIMESTAMP': "%s" % xvars['_TIMESTAMP_'],
                    'DWHO_NOTIFIER_SERVER_ID': "%s" % xvars['_SERVER_ID_'],
                    'DWHO_NOTIFIER_SOFTNAME':  "%s" % xvars['_SOFTNAME_'],
                    'DWHO_NOTIFIER_SOFTVER':   "%s" % xvars['_SOFTVER_'],
                    'DWHO_NOTIFIER_UUID':      "%s" % xvars['_UUID_']})

        return env

    @staticmethod
    def _mk_args(name, args, cargs, targs, xvars):
        r = copy.copy(args)

        if cargs:
            if not isinstance(cargs, list):
                LOG.error("invalid configuration args for notifier: %r", name)
                return None

            for x in cargs:
                if not isinstance(x, six.string_types):
                    LOG.error("invalid configuration argument %r for notifier: %r", x, name)
                    return None

                if '{' in x and '}' in x:
                    x = x.format(**xvars)
                r.append(x)

        if targs:
            if not isinstance(targs, list):
                LOG.error("invalid template args for notifier: %r", name)
                return None

            for x in targs:
                if not isinstance(x, six.string_types):
                    LOG.error("invalid template argument %r for notifier: %r", x, name)
                    return None

                if '{' in x and '}' in x:
                    x = x.format(**xvars)
                r.append(x)

        return r

    @staticmethod
    def _load_envfile(name, envfiles):
        r = {}

        if not isinstance(envfiles, list):
            LOG.error("invalid payload envfiles for notifier: %r", name)
            return r

        for envfile in envfiles:
            try:
                r.update(dotenv_values(envfile))
            except Exception as e:
                LOG.warning("unable to load envfile: %r, error: %r", envfile, e)

        return r

    def _mk_env(self, name, cenvfiles, tenvfiles, cenv, tenv, xvars):
        r   = {}
        env = []

        if tenvfiles:
            if not isinstance(tenvfiles, list):
                LOG.warning("invalid template envfiles for notifier: %r", name)
                return r

            for key, val in six.iteritems(self._load_envfile(name, tenvfiles)):
                env.append({key: val})

        if cenvfiles:
            if not isinstance(cenvfiles, list):
                LOG.warning("invalid configuration envfiles for notifier: %r", name)
                return r

            for key, val in six.iteritems(self._load_envfile(name, cenvfiles)):
                env.append({key: val})

        if cenv:
            if isinstance(cenv, dict):
                for key, val in six.iteritems(cenv):
                    env.append({key: val})
            elif not isinstance(cenv, list):
                LOG.warning("invalid configuration env for notifier: %r", name)
                return r
            else:
                env.extend(cenv)

        if tenv:
            if not isinstance(tenv, dict):
                LOG.warning("invalid template env for notifier: %r", name)
                return r

            r = tenv.copy()

        self._build_params_dict('env', env, tenv, xvars, r)

        return r

    @staticmethod
    def _proc_std(std, log, texit):
        stopped = False
        while not stopped:
            try:
                for x in iter(std.readline, b''):
                    if x != '':
                        log(x.rstrip())
            except Exception as e:
                LOG.exception(e)
                break
            finally:
                if texit.is_set():
                    stopped = True

    def __call__(self, name, cfg, uri, nvars, tpl = None):
        if not uri[2]:
            LOG.error("invalid subproc path: %r", uri[2])
            return None

        if not isinstance(tpl, dict):
            tpl = {}

        args      = [uri[2]]
        targs     = None
        tenv      = {}
        tenvfiles = []
        xvars     = {}
        timeout   = tpl.get('timeout', cfg.get('timeout', DEFAULT_TIMEOUT))

        if isinstance(tpl.get('vars'), dict):
            xvars = copy.deepcopy(tpl['vars'])

        xvars.update(copy.deepcopy(nvars))

        if tpl.get('args'):
            if cfg.get('disallow-args'):
                LOG.warning("args from template isn't allowed for notifier: %r", name)
            else:
                targs = copy.copy(tpl['args'])

        args = self._mk_args(name, args, cfg.get('args'), targs, xvars)
        if not args:
            raise ValueError("invalid args for notifier: %r" % name)

        if tpl.get('env'):
            if cfg.get('disallow-env'):
                LOG.warning("env from template isn't allowed for notifier: %r", name)
            else:
                tenv = tpl['env']

        if tpl.get('envfile'):
            if cfg.get('disallow-env'):
                LOG.warning("envfile from template isn't allowed for notifier: %r", name)
            else:
                tenvfiles = tpl['envfile']

        env = self._mk_env(name, cfg.get('envfiles'), tenvfiles, cfg.get('env'), tenv, xvars)
        if not env:
            env = {}

        if cfg.get('search_paths'):
            if not isinstance(cfg['search_paths'], list):
                LOG.warning("invalid search_paths for notifier: %r", name)
            else:
                env['PATH'] = os.path.pathsep.join(cfg['search_paths'])

        env   = self._set_default_env(env, xvars)

        texit = threading.Event()
        proc  = None

        try:
            proc  = subprocess.Popen(args,
                                     stdout = subprocess.PIPE,
                                     stderr = subprocess.PIPE,
                                     env    = env,
                                     cwd    = cfg.get('workdir'))

            to    = threading.Thread(target=self._proc_std,
                                     args=(proc.stdout, LOG.info, texit))
            to.daemon = True
            to.start()

            te    = threading.Thread(target=self._proc_std,
                                     args=(proc.stderr, LOG.error, texit))
            te.daemon = True
            te.start()

            start = time.time()

            while True:
                if proc.poll() is not None:
                    break

                if start + timeout <= time.time():
                    raise StopIteration("timeout on notifier: %r" % name)

            if proc.returncode:
                raise subprocess.CalledProcessError(proc.returncode, args[0])
        except subprocess.CalledProcessError as e:
            LOG.error("unable to push notification %r: %r, rc: %r", name, e, e.returncode)
        except Exception as e:
            LOG.error("unable to push notification %r: %r", name, e)
        finally:
            texit.set()

        try:
            if proc and proc.returncode is None:
                proc.terminate()
        except OSError:
            pass


if __name__ != "__main__":
    def _start():
        NOTIFIERS.register(DWhoNotifierHttp())
        NOTIFIERS.register(DWhoNotifierRedis())
        NOTIFIERS.register(DWhoNotifierSubprocess())
    _start()
