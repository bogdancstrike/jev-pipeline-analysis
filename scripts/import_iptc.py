#!/usr/bin/env python3
"""Import the official en-US IPTC tree as an offline, attributed snapshot (CC BY 4.0)."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import urllib.request

SOURCE = 'https://www.iptc.org/std/NewsCodes/treeview/mediatopic/mediatopic-en-US.html'


class TopicTable(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = None
        self.cell = None
        self.heading = False
        self.title = ''

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'h1':
            self.heading = True
        if tag == 'tr' and 'data-tt-id' in attrs:
            self.row = {'id': attrs['data-tt-id'], 'parent': attrs.get('data-tt-parent-id'),
                        'retired': 'retired' in attrs.get('class', '').split(), 'cells': []}
        if tag == 'td' and self.row is not None:
            self.cell = ''

    def handle_data(self, data):
        if self.heading:
            self.title += data
        if self.cell is not None:
            self.cell += data

    def handle_endtag(self, tag):
        if tag == 'h1':
            self.heading = False
        if tag == 'td' and self.cell is not None:
            self.row['cells'].append(' '.join(self.cell.split()))
            self.cell = None
        if tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def convert(html):
    parser = TopicTable()
    parser.feed(html)
    rows = {row['id']: row for row in parser.rows}
    if len(rows) != len(parser.rows):
        raise ValueError('Duplicate concept IDs in source')
    active = {key: {'id': key, 'name': row['cells'][1], 'definition': row['cells'][2]}
              for key, row in rows.items() if not row['retired'] and len(row['cells']) == 3}
    roots = []
    for key, topic in active.items():
        parent = rows[key]['parent']
        visited = {key}
        while parent and parent not in active:
            if parent in visited or parent not in rows:
                raise ValueError(f'Invalid parent for {key}')
            visited.add(parent)
            parent = rows[parent]['parent']
        if parent:
            active[parent].setdefault('children', []).append(topic)
        else:
            roots.append(topic)
    if len(roots) != 17 or len(active) < 1000:
        raise ValueError('Unexpected taxonomy size; review upstream format before replacing the snapshot')
    return {'source': SOURCE, 'version': re.search(r'\d{4}-\d{2}-\d{2}', parser.title)[0],
            'language': 'en-US', 'license': 'CC BY 4.0', 'license_url': 'https://creativecommons.org/licenses/by/4.0/',
            'attribution': 'Copyright 2026 IPTC. IPTC NewsCodes, Media Topics. Retired concepts excluded; tree serialized to JSON.',
            'source_sha256': hashlib.sha256(html.encode()).hexdigest(), 'concepts': len(active),
            'retired_excluded': sum(row['retired'] for row in rows.values()), 'tree': roots}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', help='Saved official HTML; omit to download it')
    p.add_argument('--output', default='backend/app/modules/iptc/taxonomy.json')
    args = p.parse_args()
    html = Path(args.input).read_text() if args.input else urllib.request.urlopen(SOURCE, timeout=30).read().decode()
    document = convert(html)
    Path(args.output).write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n')
    print(f"Imported {document['concepts']} active concepts, 17 roots, version {document['version']}.")
