import asyncio
import threading
import unittest
from textual.widgets import Input
from dwho.tui.textual import InputForm, ServiceDashboard

class FormServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        asyncio.get_running_loop().set_debug(False)

    async def test_form_values_are_literal_cancel_has_no_intent(self):
        app = ServiceDashboard(product='Demo', heading='Demo', columns=('Name',))
        replies = []
        async with app.run_test() as pilot:
            app.push_screen(InputForm('Inputs', [('value', 'Value', '', False)]), replies.append)
            await pilot.pause()
            app.screen.query_one(Input).value = '[bold]literal[/bold]'
            await pilot.click('#form-submit'); await pilot.pause()
            self.assertEqual(replies, [{'value': '[bold]literal[/bold]'}])
            app.push_screen(InputForm('Inputs', [('value', 'Value', '', False)]), replies.append)
            await pilot.pause(); await pilot.press('escape'); await pilot.pause()
            self.assertIsNone(replies[-1])

    async def test_background_call_serialization_and_no_retry_on_error(self):
        app = ServiceDashboard(product='Demo', heading='Demo', columns=('Name',))
        started, release = threading.Event(), threading.Event()
        errors, done = [], []
        def slow():
            started.set(); release.wait(2)
            raise ValueError('synthetic')
        async with app.run_test() as pilot:
            try:
                self.assertTrue(app.perform(slow, done.append, errors.append))
                await asyncio.to_thread(started.wait, 1)
                self.assertFalse(app.perform(lambda: 2, done.append))
                self.assertTrue(app.busy)
                release.set(); await pilot.pause()
                self.assertEqual(len(errors), 1)
                self.assertEqual(done, [])
                self.assertFalse(app.busy)
            finally:
                release.set()
