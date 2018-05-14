# -*- coding: utf-8 -*-
"""crypto helper"""

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

import base64
import random

from Crypto import Random
from Crypto.Cipher import AES

try:
    import cPickle as pickle
except ImportError:
    import pickle


class DWhoCryptoHelper(object):
    @staticmethod
    def _pad(bs, data):
        return data + (bs - len(data) % bs) * chr(bs - len(data) % bs)

    @staticmethod
    def _unpad(data):
        return data[:-ord(data[len(data)-1:])]

    @staticmethod
    def _normalize_key(secret_key):
        if not isinstance(secret_key, basestring):
            return

        xlen = len(secret_key)
        if xlen > 32:
            return secret_key[0:32]
        elif xlen > 24:
            return secret_key[0:24]

        return secret_key[0:16]

    @classmethod
    def encrypt(cls, secret_key, data):
        bs      = AES.block_size
        iv      = Random.get_random_bytes(bs)
        cipher  = AES.new(cls._normalize_key(secret_key), AES.MODE_CBC, iv)
        data    = cls._pad(bs, data)

        return base64.b64encode(iv + cipher.encrypt(data)).replace('/', '.')

    @classmethod
    def decrypt(cls, secret_key, data):
        bs      = AES.block_size
        data    = base64.b64decode(data.replace(' ', '+').replace('.', '/'))
        iv      = data[:bs]
        cipher  = AES.new(cls._normalize_key(secret_key), AES.MODE_CBC, iv)

        return cls._unpad(cipher.decrypt(data[bs:]))

    @classmethod
    def serialize(cls, secret_key, data):
        return cls.encrypt(secret_key, pickle.dumps(data))

    @classmethod
    def unserialize(cls, secret_key, data):
        return pickle.loads(cls.decrypt(secret_key, data))

if __name__ == '__main__':
    secret_key = 'Zoo1ahJah1uveeQ4Zo454'
    print DWhoCryptoHelper.unserialize(secret_key, DWhoCryptoHelper.serialize(secret_key, ('totota9', 'tutu', {'tutu': 'titi'})))
