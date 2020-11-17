# -*- coding: utf-8 -*-
# Copyright (C) 2015-2019 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""dwho.adapters.redis"""

from __future__ import absolute_import

from six import iteritems, iterkeys
from six.moves.urllib.parse import urlparse, parse_qs

from redis import Redis


class DWhoAdapterRedis(object): # pylint: disable=useless-object-inheritance
    def __init__(self, config, prefix = None, load = True):
        self.config  = config
        self.servers = {}

        if load:
            self.load(prefix)

    def load(self, prefix = None):
        for name in iterkeys(self.config['general']['redis']):
            if not prefix or name.startswith(prefix):
                self.connect(name)

    def connect(self, name):
        if not self.servers:
            self.servers = {name:
                            {'conn':    None,
                             'options': {}}}

        if self.servers[name]['conn']:
            return self.servers[name]

        has_from_url = hasattr(Redis, 'from_url')
        for key, value in iteritems(self.config['general']['redis'][name]):
            if key != 'url':
                self.servers[name]['options'][key] = value
                continue
            elif has_from_url:
                self.servers[name]['conn'] = Redis().from_url(value)
                continue

            p     = urlparse(value)
            rconf = {'host': p.hostname,
                     'port': int(p.port or 6379),
                     'db':   0}

            if p.query:
                q = parse_qs(p.query)
                if 'db' in q:
                    rconf['db'] = int(q['db'][0])

            self.servers[name]['conn'] = Redis(**rconf)

        return self.servers[name]

    def ping(self, servers = None, prefix = None):
        r = {}

        if not servers:
            servers = self.servers

        for name, server in iteritems(servers):
            if not prefix or name.startswith(prefix):
                r[name] = server['conn'].ping()

        return r

    def set_key(self, key, val, expire = None, servers = None, prefix = None):
        r = {}

        if not servers:
            servers = self.servers

        if expire is not None:
            for name, server in iteritems(servers):
                if not prefix or name.startswith(prefix):
                    r[name] = server['conn'].setex(name = key, time = expire, value = val)
        else:
            for name, server in iteritems(servers):
                if not prefix or name.startswith(prefix):
                    r[name] = server['conn'].set(key, val)

        return r

    def get_key(self, key, servers = None, prefix = None):
        if not servers:
            servers = self.servers

        for name, server in iteritems(servers):
            if (not prefix or name.startswith(prefix)) \
               and server['conn'].exists(key):
                return server['conn'].get(key)

        return None

    def del_key(self, key, servers = None, prefix = None):
        r = {}

        if not servers:
            servers = self.servers

        if not isinstance(key, (list, tuple)):
            key = [key]

        for name, server in iteritems(servers):
            if not prefix or name.startswith(prefix):
                r[name] = server['conn'].delete(*key)

        return r

    def exists(self, key, servers = None, prefix = None):
        r = {}

        if not servers:
            servers = self.servers

        if not isinstance(key, (list, tuple)):
            key = [key]

        for name, server in iteritems(servers):
            if not prefix or name.startswith(prefix):
                r[name] = server['conn'].exists(*key)

        return r

    def expire(self, key, xtime, servers = None, prefix = None):
        r = {}

        if not servers:
            servers = self.servers

        for name, server in iteritems(servers):
            if (not prefix or name.startswith(prefix)) \
               and server['conn'].exists(key):
                r[name] = server['conn'].expire(key, xtime)

        return r

    def hset_key(self, key, field, val, expire = None, servers = None, prefix = None):
        r = {}

        if not servers:
            servers = self.servers

        if expire is not None:
            for name, server in iteritems(servers):
                if not prefix or name.startswith(prefix):
                    r[name] = server['conn'].hset(key, field, val)
                    server['conn'].expire(key, expire)
        else:
            for name, server in iteritems(servers):
                if not prefix or name.startswith(prefix):
                    r[name] = server['conn'].hset(key, field, val)

        return r

    def hget_key(self, key, field, servers = None, prefix = None):
        if not servers:
            servers = self.servers

        for name, server in iteritems(servers):
            if (not prefix or name.startswith(prefix)) \
               and server['conn'].exists(key):
                return server['conn'].hget(key, field)

        return None

    def hdel_key(self, key, field, servers = None, prefix = None):
        r = {}

        if not servers:
            servers = self.servers

        if not isinstance(field, (list, tuple)):
            field = [field]

        for name, server in iteritems(servers):
            if not prefix or name.startswith(prefix):
                r[name] = server['conn'].hdel(key, *field)

        return r

    def has_key(self, key, servers = None, prefix = None):
        if not servers:
            servers = self.servers

        for name, server in iteritems(servers):
            if not prefix or name.startswith(prefix):
                return server['conn'].exists(key)

        return None

    def keys(self, pattern = '*', servers = None, prefix = None):
        r = {}

        if not servers:
            servers = self.servers

        for name, server in iteritems(servers):
            if not prefix or name.startswith(prefix):
                r[name] = server['conn'].keys(pattern)

        return r

    def sadd(self, key, member, servers = None, prefix = None):
        r = {}

        if not servers:
            servers = self.servers

        if not isinstance(member, (list, tuple)):
            member = [member]

        for name, server in iteritems(servers):
            if not prefix or name.startswith(prefix):
                r[name] = server['conn'].sadd(key, *member)

        return r

    def srem(self, key, member, servers = None, prefix = None):
        r = {}

        if not servers:
            servers = self.servers

        if not isinstance(member, (list, tuple)):
            member = [member]

        for name, server in iteritems(servers):
            if not prefix or name.startswith(prefix):
                r[name] = server['conn'].srem(key, *member)

        return r

    # pylint: disable=too-many-arguments
    def sort(self, key, start = None, num = None, by = None, get = None,
             desc = False, alpha = False, store = None,
             servers = None, prefix = None):

        r = {}

        if not servers:
            servers = self.servers

        for name, server in iteritems(servers):
            if not prefix or name.startswith(prefix):
                r[name] = server['conn'].sort(name   = key,
                                              start  = start,
                                              num    = num,
                                              by     = by,
                                              get    = get,
                                              desc   = desc,
                                              alpha  = alpha,
                                              store  = store)

        return r

    def disconnect(self, name = None, prefix = None, servers = None):
        if not servers:
            servers = self.servers

        if name:
            if not servers.get(name) or not servers[name]['conn']:
                return self

            try:
                servers[name]['conn'].connection_pool.disconnect()
            except Exception:
                pass

            servers[name]['conn'] = None

            return self

        for cname in iterkeys(self.config['general']['redis']):
            if prefix and not cname.startswith(prefix):
                continue
            elif not servers.get(cname) or not servers[cname]['conn']:
                continue

            try:
                servers[cname]['conn'].connection_pool.disconnect()
            except Exception:
                pass

            servers[cname]['conn']   = None

        return self
