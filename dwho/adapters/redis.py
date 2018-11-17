# -*- coding: utf-8 -*-
from __future__ import absolute_import

"""DWho Redis Adapter"""

__author__  = "Adrien DELLE CAVE <adc@doowan.net>"
__license__ = """
    Copyright (C) 2016-2018  doowan

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

import redis

from urlparse import urlparse, parse_qs


class DWhoAdapterRedis(object):
    def __init__(self, config, prefix = None, load = True):
        self.config  = config
        self.servers = {}

        if load:
            self.load(prefix)

    def load(self, prefix = None):
        for name in self.config['general']['redis'].iterkeys():
            if not prefix or name.startswith(prefix):
                self.connect(name)

    def connect(self, name):
        if not self.servers:
            self.servers = {name:
                            {'conn':    None,
                             'options': {}}}

        if self.servers[name]['conn']:
            return self.servers[name]

        has_from_url = hasattr(redis.Redis, 'from_url')
        for key, value in self.config['general']['redis'][name].iteritems():
            if key != 'url':
                self.servers[name]['options'][key] = value
                continue
            elif has_from_url:
                self.servers[name]['conn'] = redis.Redis().from_url(value)
                continue

            p     = urlparse(value)
            rconf = {'host': p.hostname,
                     'port': int(p.port or 6379),
                     'db':   0}

            if p.query:
                q = parse_qs(p.query)
                if 'db' in q:
                    rconf['db'] = int(q['db'][0])

            self.servers[name]['conn'] = redis.Redis(**rconf)

        return self.servers[name]

    def set_key(self, key, val, expire = None, servers = None, prefix = None):
        r = {}

        if not servers:
            servers = self.servers

        if expire is not None:
            for name, server in servers.iteritems():
                if not prefix or name.startswith(prefix):
                    r[name] = server['conn'].setex(key, val, expire)
        else:
            for name, server in servers.iteritems():
                if not prefix or name.startswith(prefix):
                    r[name] = server['conn'].set(key, val)

        return r

    def get_key(self, key, servers = None, prefix = None):
        if not servers:
            servers = self.servers

        for name, server in servers.iteritems():
            if (not prefix or name.startswith(prefix)) \
               and server['conn'].exists(key):
                return server['conn'].get(key)

    def del_key(self, key, servers = None, prefix = None):
        r = {}

        if not servers:
            servers = self.servers

        if not isinstance(key, (list, tuple)):
            key = [key]

        for name, server in servers.iteritems():
            if not prefix or name.startswith(prefix):
                r[name] = server['conn'].delete(*key)

        return r

    def exists(self, key, servers = None, prefix = None):
        r = {}

        if not servers:
            servers = self.servers

        if not isinstance(key, (list, tuple)):
            key = [key]

        for name, server in servers.iteritems():
            if not prefix or name.startswith(prefix):
                r[name] = server['conn'].exists(*key)

        return r

    def expire(self, key, xtime, servers = None, prefix = None):
        r = {}

        if not servers:
            servers = self.servers

        for name, server in servers.iteritems():
            if (not prefix or name.startswith(prefix)) \
               and server['conn'].exists(key):
                r[name] = server['conn'].expire(key, xtime)

        return r

    def hset_key(self, key, field, val, expire = None, servers = None, prefix = None):
        r = {}

        if not servers:
            servers = self.servers

        if expire is not None:
            for name, server in servers.iteritems():
                if not prefix or name.startswith(prefix):
                    r[name] = server['conn'].hset(key, field, val)
                    server['conn'].expire(key, expire)
        else:
            for name, server in servers.iteritems():
                if not prefix or name.startswith(prefix):
                    r[name] = server['conn'].hset(key, field, val)

        return r

    def hget_key(self, key, field, servers = None, prefix = None):
        if not servers:
            servers = self.servers

        for name, server in servers.iteritems():
            if (not prefix or name.startswith(prefix)) \
               and server['conn'].exists(key):
                return server['conn'].hget(key, field)

    def hdel_key(self, key, field, servers = None, prefix = None):
        r = {}

        if not servers:
            servers = self.servers

        if not isinstance(field, (list, tuple)):
            field = [field]

        for name, server in servers.iteritems():
            if not prefix or name.startswith(prefix):
                r[name] = server['conn'].hdel(key, *field)

        return r

    def has_key(self, key, servers = None, prefix = None):
        if not servers:
            servers = self.servers

        for name, server in servers.iteritems():
            if not prefix or name.startswith(prefix):
                return server['conn'].exists(key)

    def keys(self, pattern = '*', servers = None, prefix = None):
        r = {}

        if not servers:
            servers = self.servers

        for name, server in servers.iteritems():
            if not prefix or name.startswith(prefix):
                r[name] = server['conn'].keys(pattern)

        return r

    def sadd(self, key, member, servers = None, prefix = None):
        r = {}

        if not servers:
            servers = self.servers

        if not isinstance(member, (list, tuple)):
            member = [member]

        for name, server in servers.iteritems():
            if not prefix or name.startswith(prefix):
                r[name] = server['conn'].sadd(key, *member)

        return r

    def srem(self, key, member, servers = None, prefix = None):
        r = {}

        if not servers:
            servers = self.servers

        if not isinstance(member, (list, tuple)):
            member = [member]

        for name, server in servers.iteritems():
            if not prefix or name.startswith(prefix):
                r[name] = server['conn'].srem(key, *member)

        return r

    def sort(self, key, start = None, num = None, by = None, get = None,
             desc = False, alpha = False, store = None,
             servers = None, prefix = None):

        r = {}

        if not servers:
            servers = self.servers

        for name, server in servers.iteritems():
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

    def disconnect(self, name):
        if not self.servers:
            self.servers = {name:
                            {'conn':     None,
                             'options':  {}}}

        if self.servers[name]['conn']:
            try:
                self.servers[name]['conn'].disconnect()
            except Exception:
                pass

        self.servers[name]['conn']   = None

        return self
