"""Render product identities without changing semantic states or dialog behavior."""
import unittest
import asyncio

from textual.color import Color
from dwho.tui.textual import Confirmation, DashboardApp, InputForm, StatusLine
from dwho.tui.textual.theme import PALETTES, STATE_COLORS, product_theme


def contrast(first, second):
    def luminance(value):
        channels = [channel / 255 for channel in Color.parse(value).rgb]
        linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
        return sum(v * weight for v, weight in zip(linear, (.2126, .7152, .0722)))
    light, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (light + .05) / (dark + .05)


class ThemeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        asyncio.get_running_loop().set_debug(False)

    def assert_color(self, actual, expected):
        self.assertLessEqual(max(abs(a-b) for a,b in zip(actual.rgb, Color.parse(expected).rgb)), 1)

    async def check_product(self, product, key):
        app = DashboardApp(product, 'Inventory', ('NAME',), navigation=(('items', 'Items'),))
        background, surface, panel, foreground, primary, secondary, selection = PALETTES[key]
        async with app.run_test(size=(120, 36)) as pilot:
            self.assertEqual(app.theme, 'dwho-' + key)
            self.assert_color(app.screen.styles.background, background)
            self.assert_color(app.query_one('.dw-brand').styles.color, primary)
            self.assert_color(app.query_one('.dw-mode').styles.color, secondary)
            self.assert_color(app.query_one('.dw-active').styles.background, selection)
            self.assertGreaterEqual(contrast(foreground, selection), 4.5)
            self.assertGreaterEqual(contrast(primary, surface), 4.5)
            self.assertGreaterEqual(contrast(secondary, surface), 4.5)
            for state, color in STATE_COLORS.items():
                app.set_notice(state, 'Synthetic state')
                self.assertEqual(app.query_one(StatusLine).render().spans[0].style, color)
                self.assertGreaterEqual(contrast(color, panel), 4.5)
            app.push_screen(Confirmation('Review', 'Synthetic intent'))
            await pilot.pause()
            self.assert_color(app.screen.query_one('.dw-confirm').styles.background, panel)
            self.assertEqual(app.focused.id, 'dw-cancel')
            await pilot.press('escape')
            app.push_screen(InputForm('Input', [('name', 'Name', '', False)]))
            await pilot.pause()
            self.assert_color(app.screen.query_one('.dw-form').styles.background, panel)
            await pilot.press('escape')

    async def test_atraxis_cyan(self):
        await self.check_product('Atraxis', 'atraxis')

    async def test_auton_turquoise_and_orange(self):
        await self.check_product('Auton', 'auton')

    async def test_monit_steel_blue(self):
        await self.check_product('monit-docker', 'monit-docker')

    async def test_galliflow_violet(self):
        await self.check_product('Galliflow', 'galliflow')

    async def test_certlord_gold(self):
        await self.check_product('CertLord', 'certlord')

    def test_explicit_palette_and_unknown_product(self):
        self.assertEqual(product_theme('Custom name', 'auton').name, 'dwho-auton')
        self.assertEqual(product_theme('Unknown').name, 'dwho-default')
        with self.assertRaisesRegex(ValueError, 'invalid_dashboard_palette'):
            product_theme('Auton', 'missing')

    def test_theme_instances_do_not_share_mutable_variables(self):
        first = product_theme('Auton')
        second = product_theme('Auton')
        first.variables['primary-muted'] = '#ffffff'
        self.assertEqual(second.variables['primary-muted'], PALETTES['auton'][-1])
        self.assertNotEqual(product_theme('Galliflow').primary, second.primary)
        with self.assertRaises(TypeError):
            PALETTES['auton'] = PALETTES['default']
