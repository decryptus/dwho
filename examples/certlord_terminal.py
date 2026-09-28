# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only adapter example: pass a CertLord CertificateService instance.

No credentials, storage construction, HTTP module or worker startup belongs in
this example. The caller supplies an already composed and authorized service.
"""
from dwho.cli import write_json
from dwho import tui

TITLE = 'CertLord | Certificate status'


def show_index(service, site_id, screen=None, stream=None):
    records = service.index(site_id)
    if screen is None:
        write_json(records, stream=stream, sort_keys=True)
    else:
        rows = ['{} | {}'.format(domain, records[domain]) for domain in sorted(records)]
        tui.view_details(screen, TITLE, rows or ['No certificates'])
    return records
