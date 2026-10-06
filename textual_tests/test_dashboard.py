"""Optional Textual tests. Dedicated Python 3.9+ discovery root, no real services."""
import asyncio
import unittest
import subprocess
import sys

from textual.widgets import Button, DataTable, Input, Static

from dwho.tui.textual import Confirmation, DashboardApp, DetailPanel, StatusLine, TableRow, plain_text
from dwho.tui.textual.demo import Demo
from dwho.tui.textual.theme import STATE_COLORS


ROWS = [TableRow('a', ('api', '87 %'), 'api', 'CPU warning'),
        TableRow('b', ('database', '24 %'), 'database', 'Database details')]


class DashboardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        asyncio.get_running_loop().set_debug(False)

    def app(self, **kwargs):
        return DashboardApp('Product', 'Overview', ('NAME', 'CPU'),
                            navigation=(('overview', 'Overview'), ('jobs', 'Jobs')), **kwargs)

    async def test_filter_selection_and_refresh_keep_identity(self):
        app = self.app()
        async with app.run_test(size=(140, 44)) as pilot:
            app.display_rows(ROWS); await pilot.pause()
            await pilot.press('down'); await pilot.pause()
            app.display_rows(list(reversed(ROWS))); await pilot.pause()
            table = app.query_one(DataTable)
            self.assertEqual(table.cursor_row, 0)
            self.assertEqual(str(app.query_one('.dw-detail-title', Static).render()), 'database')
            await pilot.press('/'); await pilot.press('a', 'p', 'i'); await pilot.pause()
            self.assertEqual(table.row_count, 1)
            self.assertEqual(str(app.query_one('.dw-detail-title', Static).render()), 'api')
            await pilot.press('escape'); await pilot.pause()
            self.assertEqual(table.row_count, 2)

    async def test_empty_search_does_not_leave_stale_details(self):
        app = self.app()
        async with app.run_test() as pilot:
            app.display_rows(ROWS)
            app.query_one(Input).value = 'does-not-exist'; await pilot.pause()
            self.assertEqual(app.query_one(DataTable).row_count, 0)
            self.assertTrue(app.query_one('.dw-empty').display)
            self.assertEqual(str(app.query_one('.dw-detail-title', Static).render()), 'No selection')

    async def test_remote_markup_and_controls_remain_literal(self):
        app = self.app()
        dangerous = '[link=https://example.invalid]click[/link]\x1b\x07'
        async with app.run_test() as pilot:
            app.display_rows([TableRow('a', (dangerous, '1 %'), dangerous, dangerous)])
            app.set_notice('unknown', dangerous); app.set_activity(dangerous)
            await pilot.pause()
            cell = app.query_one(DataTable).get_cell_at((0, 0))
            self.assertIn('[link=', cell.plain)
            self.assertEqual(cell.spans, [])
            self.assertNotIn('\x1b', cell.plain)
            self.assertEqual(str(app.query_one('.dw-detail-text', Static).render()), plain_text(dangerous))
            self.assertEqual(str(app.query_one('#dw-activity', Static).render()), plain_text(dangerous))

    async def test_duplicate_or_wrong_shape_rows_leave_previous_view_unchanged(self):
        app = self.app()
        async with app.run_test() as pilot:
            app.display_rows(ROWS)
            for values in ([ROWS[0], ROWS[0]], [TableRow('x', ('one',), 'x', '')]):
                with self.assertRaises(ValueError): app.display_rows(values)
            self.assertEqual(app.query_one(DataTable).row_count, 2)

    async def test_small_terminal_and_resize_recover_without_data_loss(self):
        app = self.app(mode='test')
        async with app.run_test(size=(140, 44)) as pilot:
            app.display_rows(ROWS)
            await pilot.resize_terminal(60, 15); await pilot.pause()
            self.assertTrue(app.screen.has_class('dw-too-small'))
            await pilot.resize_terminal(100, 32); await pilot.pause()
            self.assertFalse(app.screen.has_class('dw-too-small'))
            self.assertTrue(app.screen.has_class('dw-compact'))
            self.assertEqual(app.query_one(DataTable).row_count, 2)
            self.assertEqual(str(app.query_one('.dw-mode', Static).render()), 'TEST MODE')

    async def test_navigation_requests_do_not_switch_views_without_owner(self):
        app = self.app()
        async with app.run_test(size=(140, 44)) as pilot:
            app.display_rows(ROWS)
            await pilot.click('#dw-nav-1'); await pilot.pause()
            self.assertTrue(app.query_one('#dw-nav-0').has_class('dw-active'))
            app.select_navigation('jobs')
            self.assertTrue(app.query_one('#dw-nav-1').has_class('dw-active'))
            self.assertEqual(app.query_one(DataTable).row_count, 2)

    async def test_confirmation_defaults_to_cancel_and_requires_explicit_accept(self):
        app = self.app(); results = []
        async with app.run_test(size=(100, 32)) as pilot:
            app.push_screen(Confirmation('Review', 'No operation is attached.'), results.append)
            await pilot.pause()
            self.assertEqual(app.focused.id, 'dw-cancel')
            await pilot.press('enter'); await pilot.pause()
            self.assertEqual(results, [False])
            app.push_screen(Confirmation('Review', 'No operation is attached.'), results.append)
            await pilot.pause(); await pilot.click('#dw-confirm'); await pilot.pause()
            self.assertEqual(results, [False, True])
            app.push_screen(Confirmation('Review', 'No operation is attached.'), results.append)
            await pilot.pause(); await pilot.press('escape'); await pilot.pause()
            self.assertEqual(results, [False, True, False])

    async def test_demo_switches_product_views_without_starting_any_action(self):
        app = Demo()
        async with app.run_test(size=(156, 48)) as pilot:
            self.assertEqual(len(app.query_one(DataTable).columns), 5)
            await pilot.click('#dw-nav-1'); await pilot.pause()
            self.assertIn('inventory', app.query_one(DataTable).get_cell_at((0, 0)).plain)
            await pilot.press('c'); await pilot.pause(); await pilot.click('#dw-confirm'); await pilot.pause()
            self.assertEqual(app.query_one('#dw-notice', StatusLine).state, 'accepted')

    def test_states_distinguish_acceptance_running_success_and_unknown(self):
        self.assertNotEqual(STATE_COLORS['accepted'], STATE_COLORS['success'])
        self.assertNotEqual(STATE_COLORS['running'], STATE_COLORS['success'])
        self.assertEqual(StatusLine('unexpected', 'untrusted').state, 'unknown')
        self.assertEqual(plain_text('a\nb\x1b', multiline=True), 'a\nb ')
        with self.assertRaises(ValueError): self.app(mode='pretend-test')

    def test_optional_ui_import_is_independent_of_framework_storage_and_curses(self):
        script = '''
import builtins
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in ('httpdis', 'redis', 'sonicprobe', 'curses'):
        raise AssertionError(name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from dwho.tui.textual import DashboardApp, Confirmation
app = DashboardApp('Independent', 'Demo', ('NAME',))
dialog = Confirmation('Review', 'No service attached')
'''
        subprocess.run([sys.executable, '-c', script], check=True)
