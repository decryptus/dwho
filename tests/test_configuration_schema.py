"""Configuration contracts use XYS without coercing values or initializing services."""
import copy
import unittest
try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

from dwho.configuration_schema import validate_configuration, DWhoConfigurationError


class ConfigurationSchemaTests(unittest.TestCase):
    def test_extensions_and_values_are_preserved_without_mutation(self):
        conf = {'general': {}, 'modules': {'custom': {'opaque': [1, None]}}, 'plugin_section': {'token': 'PRIVATE'}}
        original = copy.deepcopy(conf)
        self.assertIs(validate_configuration(conf), conf)
        self.assertEqual(conf, original)

    def test_invalid_known_fields_cannot_hide_behind_extensions(self):
        cases = [None,
                 [],
                 {'general': []},
                 {'general': {}, 'modules': 'PRIVATE'}]
        for conf in cases:
            with self.assertRaises(DWhoConfigurationError) as caught:
                validate_configuration(conf)
            self.assertNotIn('PRIVATE', str(caught.exception))

    def test_invalid_values_are_not_in_validation_logs(self):
        with patch('dwho.configuration_schema.xys.LOG') as logger:
            with self.assertRaises(DWhoConfigurationError) as caught:
                validate_configuration({'general': 'PRIVATE-CONFIGURATION-VALUE'})
        self.assertNotIn('PRIVATE-CONFIGURATION-VALUE', str(caught.exception))
        self.assertNotIn('PRIVATE-CONFIGURATION-VALUE', str(logger.mock_calls))

    def test_defaults_and_legacy_worker_modes_are_preserved(self):
        from dwho.configuration import parse_conf
        for workers in ('auto', '50%', 0, -1, 3):
            conf = parse_conf({'general': {'server_id': 'localhost', 'max_workers': workers,
                                          'subdir_levels': '12', 'web_directories': '/tmp'}})
            self.assertGreaterEqual(conf['general']['max_workers'], 1)
            self.assertEqual(conf['general']['subdir_levels'], 10)
            self.assertEqual(conf['general']['web_directories'], ['/tmp'])

    def test_file_and_environment_reject_nonmapping_before_metadata(self):
        import os
        import tempfile
        from dwho.configuration import read_conf_data
        fd, path = tempfile.mkstemp()
        try:
            with os.fdopen(fd, 'w') as stream:
                stream.write('- PRIVATE')
            with self.assertRaises(DWhoConfigurationError):
                read_conf_data(path)
            with patch.dict(os.environ, {'DWHO_XYS_TEST': '- PRIVATE'}):
                with self.assertRaises(DWhoConfigurationError):
                    read_conf_data(path + '.missing', envvar='DWHO_XYS_TEST')
        finally:
            os.unlink(path)

    def test_invalid_general_precedes_credential_reads(self):
        from dwho import config
        with patch.object(config, 'load_credentials') as credentials:
            with self.assertRaises(DWhoConfigurationError):
                config.parse_conf({'general': [], 'credentials': 'PRIVATE'}, load_creds=True)
            credentials.assert_not_called()
