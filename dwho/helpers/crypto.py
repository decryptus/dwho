# -*- coding: utf-8 -*-
# Copyright (C) 2015-2019 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""dwho.helpers.crypto"""

import base64

from six import string_types

try:
    from six.moves import cPickle as pickle
except ImportError:
    import pickle

from Crypto import Random
from Crypto.Cipher import AES


class DWhoCryptoHelper(object): # pylint: disable=useless-object-inheritance
    @staticmethod
    def _pad(bs, data):
        return data + (bs - len(data) % bs) * chr(bs - len(data) % bs)

    @staticmethod
    def _unpad(data):
        return data[:-ord(data[len(data)-1:])]

    @staticmethod
    def _normalize_key(secret_key):
        if not isinstance(secret_key, string_types):
            return None

        xlen = len(secret_key)
        if xlen > 32:
            return secret_key[0:32]

        if xlen > 24:
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
    XKEY = 'Zoo1ahJah1uveeQ4Zo454'
    print(DWhoCryptoHelper.unserialize(XKEY,
                                       DWhoCryptoHelper.serialize(
                                           XKEY,
                                           ('totota9', 'tutu', {'tutu': 'titi'}))))
