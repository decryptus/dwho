import base64
import pickle
import unittest
from Crypto.Cipher import AES
from dwho.helpers.crypto import DWhoCryptoHelper as Crypto

class CustomObject(object):
    pass

class CryptoTests(unittest.TestCase):
    def test_legacy_bytes_and_unicode_roundtrip(self):
        for data in (b'', b'hello\x00\xff', u'caf\u00e9'):
            encoded = Crypto.encrypt('a' * 32, data)
            self.assertIsInstance(encoded, bytes)
            self.assertEqual(Crypto.decrypt('a' * 32, encoded), Crypto._bytes(data))

    def test_historical_key_truncation_and_wire_format(self):
        for length, actual in [(16, 16), (24, 16), (25, 24), (32, 24), (33, 32)]:
            key = b'a' * length
            # Independent historical CBC writer, deterministic IV and PKCS7.
            iv = b'0' * 16
            raw = iv + AES.new(key[:actual], AES.MODE_CBC, iv).encrypt(b'hello' + b'\x0b' * 11)
            token = base64.b64encode(raw).replace(b'/', b'.')
            self.assertEqual(Crypto.decrypt(key, token), b'hello')
            encoded = Crypto.encrypt(key, b'hello')
            raw = base64.b64decode(encoded.replace(b'.', b'/'))
            self.assertEqual(AES.new(key[:actual], AES.MODE_CBC, raw[:16]).decrypt(raw[16:]), b'hello' + b'\x0b' * 11)

    def test_pickle_data_and_explicit_custom_object_trust(self):
        data = {'items': [1, None, True, u'text'], 'tuple': (2, 3), 'bytes': b'\xff', 'set': set([1, 2])}
        self.assertEqual(Crypto.unserialize('k'*16, Crypto.serialize('k'*16, data)), data)
        token = Crypto.serialize('k'*16, CustomObject())
        with self.assertRaises(pickle.UnpicklingError):
            Crypto.unserialize('k'*16, token)
        self.assertIsInstance(Crypto.unserialize('k'*16, token, trusted=True), CustomObject)

    def test_invalid_padding_and_short_ciphertext(self):
        for data in (b'', b'\x00', b'abc\x02'):
            with self.assertRaises(ValueError):
                Crypto._unpad(data)
        with self.assertRaises(ValueError):
            Crypto.decrypt('k'*16, b'YWJj')

    def test_authenticated_roundtrip_and_tamper_rejection(self):
        token = Crypto.encrypt_authenticated(b'k'*32, b'hello')
        self.assertEqual(Crypto.decrypt_authenticated(b'k'*32, token), b'hello')
        raw = base64.b64decode(token[len(Crypto.AUTH_PREFIX):])
        for position in (0, 16, 32):
            damaged = bytearray(raw); damaged[position] ^= 1
            modified = Crypto.AUTH_PREFIX + base64.b64encode(damaged)
            with self.assertRaises(ValueError):
                Crypto.decrypt_authenticated(b'k'*32, modified)
        with self.assertRaises(ValueError):
            Crypto.decrypt_authenticated(b'z'*32, token)
        with self.assertRaises(ValueError):
            Crypto.decrypt_authenticated(b'k'*32, Crypto.encrypt(b'k'*32, b'hello'))

    def test_authenticated_json(self):
        data = {'hello': [1, u'caf\u00e9']}
        self.assertEqual(Crypto.unserialize_authenticated(b'k'*16, Crypto.serialize_authenticated(b'k'*16, data)), data)
