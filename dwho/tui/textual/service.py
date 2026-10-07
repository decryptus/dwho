"""Serialized, non-blocking presentation calls; no retry or business policy."""
import asyncio

from .dashboard import DashboardApp


class ServiceDashboard(DashboardApp):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.busy = False

    def perform(self, call, done, failed=None, label='Reading data...'):
        if self.busy:
            return False
        self.busy = True
        self.set_notice('running', label)

        async def execute():
            try:
                result = await asyncio.to_thread(call)
            except Exception as error:
                self.busy = False
                if self.is_running:
                    if failed is not None:
                        failed(error)
                    else:
                        self.set_notice('warning', 'Request did not complete. Refresh before retrying; outcome may be uncertain.')
            else:
                self.busy = False
                if self.is_running:
                    done(result)
        self.run_worker(execute(), exit_on_error=False)
        return True

    def action_quit(self):
        if self.busy:
            self.notify('A request is in progress. Wait for its result before closing.', severity='warning')
        else:
            self.exit()
