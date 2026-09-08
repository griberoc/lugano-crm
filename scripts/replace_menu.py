"""Explicit, backed-up catalog replacement. Never changes orders or order items.

Dry run by default. Application is restricted to the named Supabase project.
HTTP failures stop execution; the journal and original products allow recovery.
New rows use deterministic IDs to identify this import unambiguously.
"""
import argparse
import csv
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5

import httpx

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'https://docs.google.com/presentation/d/1aPPqLHiuP25wFoteToWcxSQZZOkaOaSVayoh8P6MHKE'


def read_menu(path):
    products = []
    seen = set()
    with path.open(encoding='utf-8-sig', newline='') as source:
        for row in csv.DictReader(source):
            if None in row or any(row[key] is None for key in row):
                raise ValueError('Malformed CSV row')
            identity = row['category'] + '/' + row['name']
            price = Decimal(row['price'])
            if identity in seen or not price.is_finite() or price <= 0 or price != price.quantize(Decimal('.01')):
                raise ValueError('Duplicate product or invalid price: ' + identity)
            if not 1 <= int(row['slide']) <= 27:
                raise ValueError('Invalid source slide')
            seen.add(identity)
            products.append(dict(id=str(uuid5(NAMESPACE_URL, SOURCE + '/' + identity)),
                                 name=row['name'], category=row['category'],
                                 price=str(price), description=row['description'] or None,
                                 image_url=None, available=True))
    if not products:
        raise ValueError('Empty menu')
    return products


def classify(products, referenced_ids, new_ids):
    old = [p for p in products if p['id'] not in new_ids]
    return ([p for p in old if p['id'] in referenced_ids],
            [p for p in old if p['id'] not in referenced_ids])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('--project-ref', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    env = {}
    for line in args.env_file.read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.strip().startswith('#'):
            key, value = line.split('=', 1)
            env[key.strip()] = value.strip().strip('\"').strip("'")
    url = env['SUPABASE_URL'].rstrip('/')
    if urlparse(url).hostname != args.project_ref + '.supabase.co':
        raise ValueError('Project mismatch; no mutation performed')
    key = env['SUPABASE_SERVICE_ROLE_KEY']
    menu = read_menu(ROOT / 'data/menu-sao-luis-2026.csv')
    ids = {p['id'] for p in menu}
    with httpx.Client(base_url=url + '/rest/v1/', headers={
        'apikey': key, 'Authorization': 'Bearer ' + key,
        'Prefer': 'return=representation'}, timeout=45) as client:
        def request(method, table, **kwargs):
            response = client.request(method, table, **kwargs)
            if response.is_error:
                # Never print credentials, customer data, or response bodies.
                raise RuntimeError(f'{method} {table.split("?")[0]} failed: HTTP {response.status_code}')
            return response.json() if response.content else []

        def read_all(table, select='*', order='id'):
            rows = []
            for offset in range(0, 1000000, 1000):
                batch = request('GET', table, params={'select': select, 'order': order,
                                                     'offset': offset, 'limit': 1000})
                rows.extend(batch)
                if len(batch) < 1000:
                    return rows
            raise RuntimeError('Pagination limit exceeded')

        existing = read_all('products')
        references = {p['product_id'] for p in read_all('order_items', 'id,product_id')}
        archive, delete = classify(existing, references, ids)
        imported = [p for p in existing if p['id'] in ids]
        summary = dict(project=args.project_ref, new_products=len(menu),
                       categories=len({p['category'] for p in menu}),
                       archive=len(archive), delete=len(delete), already_imported=len(imported))
        print(json.dumps(summary))
        if not args.apply:
            return
        if imported:
            raise RuntimeError('Import IDs already exist. Inspect journal before retrying; no mutation performed.')
        folder = ROOT / 'backups' / ('menu-' + datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ'))
        folder.mkdir(parents=True)
        backup = dict(project=args.project_ref, source=SOURCE, products=existing,
                      new_products=menu, archive_ids=[p['id'] for p in archive],
                      delete_ids=[p['id'] for p in delete])
        (folder / 'before.json').write_text(json.dumps(backup, ensure_ascii=False, indent=2), encoding='utf-8')
        if json.loads((folder / 'before.json').read_text(encoding='utf-8')) != backup:
            raise RuntimeError('Backup verification failed')
        def log(phase, **data):
            with (folder / 'journal.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(dict(phase=phase, **data)) + '\n')
                stream.flush()
        log('backup_verified', **summary)
        # Prepare all new products without exposing a partially inserted menu.
        request('POST', 'products', json=[{**p, 'available': False} for p in menu])
        log('new_products_prepared')
        old_ids = [p['id'] for p in archive + delete]
        if old_ids:
            request('PATCH', 'products', params={'id': 'in.(' + ','.join(old_ids) + ')'}, json={'available': False})
        log('old_products_withdrawn')
        request('PATCH', 'products', params={'id': 'in.(' + ','.join(sorted(ids)) + ')'}, json={'available': True})
        log('new_products_published')
        # Re-read references immediately before deletion. FK RESTRICT also protects races.
        current_references = {p['product_id'] for p in read_all('order_items', 'id,product_id')}
        deleted = 0
        for product in delete:
            if product['id'] in current_references:
                log('preserved_new_reference', product_id=product['id'])
                continue
            result = request('DELETE', 'products', params={'id': 'eq.' + product['id']})
            if len(result) != 1:
                raise RuntimeError('Unexpected deletion count; stopped')
            deleted += 1
            log('deleted', product_id=product['id'])
        actual = read_all('products')
        active = {p['id']: p for p in actual if p['available']}
        if set(active) != ids:
            raise RuntimeError('Active catalog ID verification failed')
        for expected in menu:
            found = active[expected['id']]
            if any(found[k] != expected[k] for k in ('name', 'category', 'description')) or Decimal(str(found['price'])) != Decimal(expected['price']):
                raise RuntimeError('Catalog content verification failed')
        remaining_refs = {p['product_id'] for p in read_all('order_items', 'id,product_id')}
        if not references <= remaining_refs:
            raise RuntimeError('Historical references changed; investigate')
        log('verified', active=len(active), deleted=deleted, archived=len(actual)-len(active))
        print(json.dumps(dict(verified=True, active=len(active), deleted=deleted,
                              archived=len(actual)-len(active), backup=str(folder))))


if __name__ == '__main__':
    main()
