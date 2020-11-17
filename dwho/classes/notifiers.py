# -*- coding: utf-8 -*-
# Copyright (C) 2015-2019 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""dwho.classes.notifiers"""

import abc
import copy
import json
import logging
import os
import re
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

from six import iteritems, string_types
from six.moves.urllib import request as urlrequest

from dwho.adapters.redis import DWhoAdapterRedis
from dwho.config import get_softname, get_softver
from dwho.classes.abstract import DWhoAbstractHelper


LOG = logging.getLogger('dwho.notifiers')

HTTP_ALLOWED_METHODS = ('delete', 'head', 'get', 'patch', 'post', 'put')
DEFAULT_TIMEOUT      = 30
PARSE_TAGS           = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_\-\.]{1,29}[a-zA-Z0-9]$').match


class DWhoNotifiers(dict):
    def register(self, notifier):
        if not isinstance(notifier, DWhoNotifierBase):
            raise TypeError("Invalid Notifier class. (class: %r)" % notifier)

        if helpers.has_len(notifier.SCHEME):
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
        self.notif_names    = set()
        self.server_id      = server_id or getfqdn()
        self.workerpool     = None
        self._lock          = threading.Lock()

        if config_path:
            self.load(config_path)

    @staticmethod
    def _parse_tags(tags, name = None, default = 'all'):
        r = set()

        if not isinstance(tags, (list, set, tuple)):
            if tags is not None:
                if name:
                    LOG.warning("invalid tags configuration in %s", name)
                else:
                    LOG.warning("invalid tags")
            r.add(default)
            return r

        for tag in tags:
            if not helpers.has_len(tag):
                LOG.warning("invalid tag type: %r", tag)
                continue

            m = PARSE_TAGS(tag.strip())
            if not m:
                LOG.warning("invalid tag: %r", tag)
                continue

            r.add(m.group(0))

        if not r:
            r.add(default)

        return r

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

                self.notif_names.add(name)
                self.notifications[name] = {'cfg': cfg,
                                            'tpl': None,
                                            'tags': None,
                                            'notifiers': []}

                ref = self.notifications[name]
                ref['tags'] = self._parse_tags(cfg['general'].get('tags'), name)

                if cfg['general'].get('template') and os.path.isfile(cfg['general']['template']):
                    with open(cfg['general']['template'], 'r') as t:
                        ref['tpl'] = t.read()

                uri_scheme = urisup.uri_help_split(cfg['general']['uri'])[0].lower()

                if uri_scheme not in NOTIFIERS:
                    raise NotImplementedError("unsupported URI scheme: %r" % uri_scheme)

                ref['notifiers'] = NOTIFIERS[uri_scheme]

            if f:
                f.close()

    def reset(self):
        self.notifications = {}
        self.notif_names = set()
        return self

    def _run(self, xvars = None, names = None, tags = None):
        if not xvars:
            xvars = {}

        if helpers.has_len(names):
            names = set([names])

        if not names or not isinstance(names, (list, tuple, set)):
            names = self.notif_names

        tags = self._parse_tags(tags)

        nvars                = copy.deepcopy(xvars)
        nvars['_ENV_']       = copy.deepcopy(os.environ)
        nvars['_GMTIME_']    = datetime.utcnow()
        nvars['_HOSTNAME_']  = getfqdn()
        nvars['_SERVER_ID_'] = self.server_id
        nvars['_SOFTNAME_']  = get_softname()
        nvars['_SOFTVER_']   = get_softver()
        nvars['_TAGS_']      = tags
        nvars['_TIME_']      = datetime.now()
        nvars['_TIMESTAMP_'] = time.time()
        nvars['_UUID_']      = "%s" % uuid.uuid4()
        nvars['_VARS_']      = copy.deepcopy(xvars)

        if not self.workerpool:
            self.workerpool = WorkerPool(max_workers = 1,
                                         name = 'notifiers')

        for name in names:
            if name not in self.notifications:
                LOG.warning("unable to find notifier: %r", name)
                continue

            notification = self.notifications[name]

            if not notification['cfg']['general'].get('enabled', True):
                continue

            if 'always' in notification['tags']:
                LOG.debug("'always' tag found. (notifier: %r)", name)
            elif 'all' in tags and 'never' in notification['tags']:
                LOG.debug("'never' tag found. (notifier: %r)", name)
            else:
                common_tags = tags.intersection(notification['tags'])
                if common_tags:
                    LOG.debug("common tags found %r. (notifier: %r)", list(common_tags), name)
                else:
                    LOG.debug("no common tag found. (notifier: %r)", name)
                    continue

            nvars['_NAME_'] = name

            tpl = None
            if notification['tpl']:
                tpl = json.loads(Template(notification['tpl'],
                                          imports = ['import json',
                                                     'from escapejson import escapejson',
                                                     'from os import environ as ENV']).render(**nvars))

            cfg = notification['cfg'].copy()
            cfg['general']['uri'] = Template(cfg['general']['uri']).render(**nvars)
            uri = urisup.uri_help_split(cfg['general']['uri'])

            for notifier in notification['notifiers']:
                if not cfg['general'].get('async'):
                    notifier(name, cfg, uri, nvars, tpl)
                    continue

                self.workerpool.run_args(notifier,
                                         _name_ = "notifier:%s" % name,
                                         name   = name,
                                         cfg    = cfg,
                                         uri    = uri,
                                         nvars  = nvars,
                                         tpl    = tpl)

        while self.workerpool:
            if self.workerpool.killable():
                self.workerpool.killall(0)
                self.workerpool = None
            time.sleep(0.5)

    def __call__(self, xvars = None, names = None, tags = None):
        with self._lock:
            try:
                self._run(xvars, names, tags)
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
                raise ValueError("invalid HTTP method: %r. (notifier: %r)" % (tpl['method'], name))

        if isinstance(tpl.get('auth'), dict):
            auth = tpl['auth']

        if 'headers' in tpl:
            headers = tpl['headers']

        if 'payload' in tpl:
            payload = tpl['payload']

        if not isinstance(headers, dict):
            headers = {}

        if headers:
            req = urlrequest.Request("http://127.0.0.1", data="", headers=headers)
            headers = req.headers

            if isinstance(payload, dict) \
               and headers.get('Content-type') == 'application/json':
                payload = json.dumps(payload)

        try:
            r = getattr(requests, method)(cfg['general']['uri'],
                                          auth    = auth,
                                          headers = headers,
                                          data    = payload,
                                          timeout = timeout,
                                          verify  = verify)

            if 200 <= r.status_code < 300:
                LOG.info("notification pushed. (notifier: %r, statuscode: %r)", name, r.status_code)
                return True

            LOG.error("unable to push notification. (notifier: %r, error: %r)", name, r.text)
        except Exception as e:
            LOG.error("unable to push notification. (notifier: %r, error: %r)", name, e)

        return None


class DWhoNotifierRedis(DWhoNotifierBase):
    SCHEME = ('redis',)

    def __call__(self, name, cfg, uri, nvars, tpl):
        config = {'general':
                  {'redis':
                   {'notifier': cfg['general'].get('options') or {}}}}
        config['general']['redis']['notifier']['url'] = cfg['general']['uri']

        if not tpl or not isinstance(tpl, dict):
            LOG.error("missing redis template. (notifier: %r)", name)
            return

        adapter_redis = None

        try:
            adapter_redis = DWhoAdapterRedis(config, prefix = 'notifier')
            adapter_redis.set_key(tpl['key'], json.dumps(tpl['value']))
        except Exception as e:
            LOG.error("unable to push notification. (notifier: %r, error: %r)", name, e)
        else:
            LOG.info("notification pushed. (notifier: %r)", name)
        finally:
            if adapter_redis:
                adapter_redis.disconnect(prefix = 'notifier')


class DWhoNotifierSubprocess(DWhoNotifierBase):
    SCHEME = ('subproc',)

    @staticmethod
    def _set_default_env(env, xvars):
        env.update({'DWHO_NOTIFIER':           'true',
                    'DWHO_NOTIFIER_HOSTNAME':  "%s" % getfqdn(),
                    'DWHO_NOTIFIER_GMTIME':    "%s" % xvars['_GMTIME_'],
                    'DWHO_NOTIFIER_NAME':      "%s" % xvars['_NAME_'],
                    'DWHO_NOTIFIER_TAGS':      "%s" % ','.join(xvars['_TAGS_']),
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
                LOG.error("invalid configuration args. (notifier: %r)", name)
                return None

            for x in cargs:
                if not isinstance(x, string_types):
                    LOG.error("invalid configuration argument %r. (notifier: %r)", x, name)
                    return None

                if '{' in x and '}' in x:
                    x = x.format(**xvars)
                r.append(x)

        if targs:
            if not isinstance(targs, list):
                LOG.error("invalid template args. (notifier: %r)", name)
                return None

            for x in targs:
                if not isinstance(x, string_types):
                    LOG.error("invalid template argument %r. (notifier: %r)", x, name)
                    return None

                if '{' in x and '}' in x:
                    x = x.format(**xvars)
                r.append(x)

        return r

    @staticmethod
    def _load_envfile(name, envfiles):
        r = {}

        if not isinstance(envfiles, list):
            LOG.error("invalid payload envfiles. (notifier: %r)", name)
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
                LOG.warning("invalid template envfiles. (notifier: %r)", name)
                return r

            for key, val in iteritems(self._load_envfile(name, tenvfiles)):
                env.append({key: val})

        if cenvfiles:
            if not isinstance(cenvfiles, list):
                LOG.warning("invalid configuration envfiles. (notifier: %r)", name)
                return r

            for key, val in iteritems(self._load_envfile(name, cenvfiles)):
                env.append({key: val})

        if cenv:
            if isinstance(cenv, dict):
                for key, val in iteritems(cenv):
                    env.append({key: val})
            elif not isinstance(cenv, list):
                LOG.warning("invalid configuration env. (notifier: %r)", name)
                return r
            else:
                env.extend(cenv)

        if tenv:
            if not isinstance(tenv, dict):
                LOG.warning("invalid template env. (notifier: %r)", name)
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
                LOG.warning("args from template isn't allowed. (notifier: %r)", name)
            else:
                targs = copy.copy(tpl['args'])

        args = self._mk_args(name, args, cfg.get('args'), targs, xvars)
        if not args:
            raise ValueError("invalid args. (notifier: %r)" % name)

        if tpl.get('env'):
            if cfg.get('disallow-env'):
                LOG.warning("env from template isn't allowed. (notifier: %r)", name)
            else:
                tenv = tpl['env']

        if tpl.get('envfile'):
            if cfg.get('disallow-env'):
                LOG.warning("envfile from template isn't allowed. (notifier: %r)", name)
            else:
                tenvfiles = tpl['envfile']

        env = self._mk_env(name, cfg.get('envfiles'), tenvfiles, cfg.get('env'), tenv, xvars)
        if not env:
            env = {}

        if cfg.get('search_paths'):
            if not isinstance(cfg['search_paths'], list):
                LOG.warning("invalid search_paths. (notifier: %r)", name)
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
                    raise StopIteration("timeout. (notifier: %r)" % name)

            if proc.returncode:
                raise subprocess.CalledProcessError(proc.returncode, args[0])
            LOG.info("notification pushed. (notifier: %r, returncode: %r)", name, proc.returncode)
        except subprocess.CalledProcessError as e:
            LOG.error("unable to push notification. (notifier: %r, returncode: %r, error: %r)", name, e.returncode, e)
        except Exception as e:
            LOG.error("unable to push notification. (notifier: %r, error: %r)", name, e)
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
