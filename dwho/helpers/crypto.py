# -*- coding: utf-8 -*-
# Copyright (C) 2015-2026 Adrien Delle Cave
# SPDX-License-Identifier: GPL-3.0-or-later
"""Legacy CBC compatibility and opt-in authenticated encryption."""
import base64
import binascii
import io
import json
import pickle

from six import binary_type, text_type, int2byte
from Crypto import Random
from Crypto.Cipher import AES


def _legacy_bytes(value, encoding):
    if encoding != 'latin1':
        raise pickle.UnpicklingError('Unsupported bytes encoding')
    return value.encode('latin1')


class _DataUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if module in ('__builtin__', 'builtins') and name in ('set', 'frozenset', 'complex'):
            return {'set': set, 'frozenset': frozenset, 'complex': complex}[name]
        if module == '_codecs' and name == 'encode':
            return _legacy_bytes
        raise pickle.UnpicklingError('Custom pickle globals require trusted=True')


class DWhoCryptoHelper(object):
    AUTH_PREFIX = b'dwho-eax-v1:'

    @staticmethod
    def _bytes(data):
        if isinstance(data, text_type):
            return data.encode('utf-8')
        if isinstance(data, binary_type):
            return data
        raise TypeError('Expected text or bytes')

    @classmethod
    def _pad(cls, bs, data):
        data = cls._bytes(data)
        count = bs - len(data) % bs
        return data + int2byte(count) * count

    @staticmethod
    def _unpad(data):
        if not data:
            raise ValueError('Invalid CBC padding')
        count = ord(data[-1:])
        if count < 1 or count > AES.block_size or data[-count:] != int2byte(count) * count:
            raise ValueError('Invalid CBC padding')
        return data[:-count]

    @classmethod
    def _normalize_key(cls, secret_key):
        # Preserve historical truncation, including exactly 24/32 byte keys.
        key = cls._bytes(secret_key)
        size = 32 if len(key) > 32 else 24 if len(key) > 24 else 16
        key = key[:size]
        if len(key) not in (16, 24, 32):
            raise ValueError('Legacy key must contain at least 16 bytes')
        return key

    @classmethod
    def encrypt(cls, secret_key, data):
        """Legacy CBC format. Use encrypt_authenticated for new protocols."""
        iv = Random.get_random_bytes(AES.block_size)
        cipher = AES.new(cls._normalize_key(secret_key), AES.MODE_CBC, iv)
        return base64.b64encode(iv + cipher.encrypt(cls._pad(AES.block_size, data))).replace(b'/', b'.')

    @classmethod
    def decrypt(cls, secret_key, data):
        """Decode legacy CBC and return bytes; does not authenticate the data."""
        data = cls._bytes(data).replace(b' ', b'+').replace(b'.', b'/')
        try:
            data = base64.b64decode(data)
        except (TypeError, binascii.Error):
            raise ValueError('Invalid CBC encoding')
        bs = AES.block_size
        if len(data) < 2 * bs or len(data) % bs:
            raise ValueError('Invalid CBC length')
        cipher = AES.new(cls._normalize_key(secret_key), AES.MODE_CBC, data[:bs])
        return cls._unpad(cipher.decrypt(data[bs:]))

    @classmethod
    def serialize(cls, secret_key, data):
        return cls.encrypt(secret_key, pickle.dumps(data, protocol=2))

    @classmethod
    def unserialize(cls, secret_key, data, trusted=False):
        """Read legacy data; custom Python objects require explicit trust."""
        plaintext = cls.decrypt(secret_key, data)
        if trusted:
            return pickle.loads(plaintext)
        return _DataUnpickler(io.BytesIO(plaintext)).load()

    @classmethod
    def _authenticated_key(cls, secret_key):
        key = cls._bytes(secret_key)
        if len(key) not in (16, 24, 32):
            raise ValueError('Authenticated key must be exactly 16, 24 or 32 bytes')
        return key

    @classmethod
    def encrypt_authenticated(cls, secret_key, data):
        cipher = AES.new(cls._authenticated_key(secret_key), AES.MODE_EAX,
                         nonce=Random.get_random_bytes(16), mac_len=16)
        cipher.update(cls.AUTH_PREFIX)
        ciphertext, tag = cipher.encrypt_and_digest(cls._bytes(data))
        return cls.AUTH_PREFIX + base64.b64encode(cipher.nonce + tag + ciphertext)

    @classmethod
    def decrypt_authenticated(cls, secret_key, data):
        data = cls._bytes(data)
        if not data.startswith(cls.AUTH_PREFIX):
            raise ValueError('Expected authenticated dwho-eax-v1 data')
        encoded = data[len(cls.AUTH_PREFIX):]
        try:
            payload = base64.b64decode(encoded)
        except (TypeError, binascii.Error):
            raise ValueError('Invalid authenticated encoding')
        if base64.b64encode(payload) != encoded or len(payload) < 32:
            raise ValueError('Invalid authenticated payload')
        cipher = AES.new(cls._authenticated_key(secret_key), AES.MODE_EAX,
                         nonce=payload[:16], mac_len=16)
        cipher.update(cls.AUTH_PREFIX)
        return cipher.decrypt_and_verify(payload[32:], payload[16:32])

    @classmethod
    def serialize_authenticated(cls, secret_key, data):
        """JSON data only; never invokes pickle constructors."""
        return cls.encrypt_authenticated(secret_key, json.dumps(data, allow_nan=False))

    @classmethod
    def unserialize_authenticated(cls, secret_key, data):
        return json.loads(cls.decrypt_authenticated(secret_key, data).decode('utf-8'))
