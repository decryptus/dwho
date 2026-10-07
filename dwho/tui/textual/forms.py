"""Small reusable input dialogs. Values are intent, never authorization."""
from rich.text import Text
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from .widgets import plain_text


class InputForm(ModalScreen):
    """Fields are (key, label, initial value, secret); cancel returns None."""
    DEFAULT_CSS = '''
    InputForm { align: center middle; background: #000000 65%; }
    .dw-form { width: 80; max-width: 95%; height: auto; max-height: 90%;
        padding: 1 2; background: #14253b; border: round #638fb4; }
    .dw-fields { height: auto; max-height: 25; }
    .dw-form Static { height: auto; margin-top: 1; }
    .dw-form Input { height: 3; }
    .dw-form-buttons { height: 3; align: right middle; margin-top: 1; }
    .dw-form-buttons Button { margin-left: 1; }
    '''
    BINDINGS = [('escape', 'cancel', 'Cancel')]

    def __init__(self, title, fields, hint='', submit='Continue'):
        super().__init__()
        self.heading, self.fields, self.hint, self.submit_label = title, tuple(fields), hint, submit

    def compose(self):
        with Vertical(classes='dw-form'):
            yield Static(plain_text(self.heading), markup=False)
            with VerticalScroll(classes='dw-fields'):
                if self.hint:
                    yield Static(plain_text(self.hint, multiline=True), markup=False)
                for index, (_, label, value, secret) in enumerate(self.fields):
                    yield Static(plain_text(label), markup=False)
                    yield Input(value=value, password=secret, max_length=65536, id='field-%s' % index)
            with Horizontal(classes='dw-form-buttons'):
                yield Button('Cancel', id='form-cancel')
                yield Button(Text(plain_text(self.submit_label)), id='form-submit', variant='primary')

    def action_cancel(self):
        self.dismiss(None)

    def on_button_pressed(self, event):
        event.stop()
        if event.button.id == 'form-submit':
            self.dismiss({key: self.query_one('#field-%s' % index, Input).value
                          for index, (key, _, _, _) in enumerate(self.fields)})
        else:
            self.action_cancel()
