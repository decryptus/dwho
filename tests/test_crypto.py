import base64
import pickle
import unittest
import warnings
from Crypto.Cipher import AES
from dwho.helpers.crypto import DWhoCryptoHelper as Crypto

class CustomObject(object):
    pass

class CryptoTests(unittest.TestCase):
    def test_legacy_writes_warn_once_per_call(self):
        key = b'k' * 16
        for writer, data in ((Crypto.encrypt, b'old'), (Crypto.serialize, {'old': 1})):
            with warnings.catch_warnings(record=True) as seen:
                warnings.simplefilter('always', DeprecationWarning)
                writer(key, data)
            self.assertEqual(len(seen), 1)
            self.assertIs(seen[0].category, DeprecationWarning)

    def test_migrate_records_written_by_0_3_66(self):
        # Fixed outputs from the published 0.3.66 writers. A 32-byte legacy key
        # exercises CBC's historical truncation when reading these records.
        old_key = b'legacy-fixture-key-0123456789ABC'
        new_key = b'K' * 32
        raw_token = b'rNeYnCghbVQEMQ7BCCKbjW2gd9d1Yzvczmkjs5btx5g='
        pickle_token = b'5eyBM1b0WlPSLs5MoRPPMU5CsQyqHDMuRPvUmWkXnMb4BDp4nFjyDaY4+7Lo.RdM'
        with warnings.catch_warnings():
            warnings.simplefilter('error', DeprecationWarning)
            raw = Crypto.decrypt(old_key, raw_token)
            record = Crypto.unserialize(old_key, pickle_token)
            self.assertEqual(raw, b'archive\x00\xff')
            self.assertEqual(record, {'count': 7})
            self.assertEqual(Crypto.decrypt_authenticated(
                new_key, Crypto.encrypt_authenticated(new_key, raw)), raw)
            self.assertEqual(Crypto.unserialize_authenticated(
                new_key, Crypto.serialize_authenticated(new_key, record)), record)

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
