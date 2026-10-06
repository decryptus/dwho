# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Synthetic terminal demo. No connections, files, jobs or interventions."""
from . import Confirmation, DashboardApp, TableRow

CONTAINER_ROWS = (
    TableRow('api', ('api-gateway', 'edge-01', '87 %', '64 %', 'WARNING'), 'api-gateway',
             'WARNING: CPU above 85 %\n\nServer: edge-01\nCPU: 87 %\nMemory: 64 %\n\nSynthetic observation.\nNo intervention started.'),
    TableRow('db', ('postgres', 'data-01', '24 %', '58 %', 'HEALTHY'), 'postgres',
             'HEALTHY\n\nServer: data-01\nCPU: 24 %\nMemory: 58 %\n\nSynthetic observation.'),
    TableRow('export', ('exporter', 'edge-01', '11 %', '21 %', 'HEALTHY'), 'exporter',
             'HEALTHY\n\nServer: edge-01\nCPU: 11 %\nMemory: 21 %\n\nSynthetic observation.'),
)
JOB_ROWS = (
    TableRow('job-01', ('inventory', 'worker-01', 'RUNNING', '-', 'JOB 001'), 'inventory / JOB 001',
             'IN PROGRESS\n\nAccepted: yes\nExecution: running\nResult: unavailable\n\nSynthetic job. Acceptance is not success.'),
    TableRow('job-02', ('backup', 'worker-02', 'FAILED', '1', 'JOB 002'), 'backup / JOB 002',
             'FAILED\n\nExit code: 1\nSynthetic diagnostic: destination unavailable.'),
    TableRow('job-03', ('health-check', 'worker-01', 'SUCCESS', '0', 'JOB 003'), 'health-check / JOB 003',
             'SUCCESS\n\nExit code: 0\nSynthetic output: checks completed.'),
)


class Demo(DashboardApp):
    BINDINGS = DashboardApp.BINDINGS + [('c', 'review', 'Review demo')]

    def __init__(self):
        super(Demo, self).__init__(
            product='DWho / Textual', heading='One terminal language for your tools.',
            subtitle='SHARED PRESENTATION / DEMONSTRATION', mode='test',
            columns=('RESOURCE', 'HOST', 'CPU / STATE', 'RAM / EXIT', 'STATUS / ID'),
            navigation=(('containers', 'Containers'), ('jobs', 'Jobs')),
            metrics=(('RESOURCES', '03', 'synthetic containers', 'info'),
                     ('ATTENTION', '01', 'CPU warning', 'warning'),
                     ('ACTIONS', '00', 'no execution', 'info')))

    def on_mount(self):
        self.display_rows(CONTAINER_ROWS)
        self.set_notice('info', 'DEMO: synthetic data only. No service is connected.')
        self.set_activity('22:51  WARNING  api-gateway: CPU threshold exceeded\n'
                          '22:50  INFO     Snapshot loaded from demo fixtures')

    def on_dashboard_app_navigation_requested(self, message):
        self.select_navigation(message.key)
        self.query_one('Input').value = ''
        self.display_rows(CONTAINER_ROWS if message.key == 'containers' else JOB_ROWS)

    def action_review(self):
        self.push_screen(Confirmation('Review a simulated request',
            'Target: demo only\nAction: record confirmation intent\n\n'
            'No job, command or network request will be started.', confirm_label='Confirm demo'),
            self.reviewed)

    def reviewed(self, accepted):
        self.set_notice('accepted' if accepted else 'info',
                        'Demo intent accepted; no action executed.' if accepted else 'Demo cancelled; no action executed.')


if __name__ == '__main__':
    Demo().run()
