"""Upload converted JSON into PostgreSQL using a single transaction."""
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import hashlib
from datetime import date
from json_compression import load_json


def parse_period(value):
    if type(value) is date:
        return value
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('Choose a valid reporting period date (YYYY-MM-DD)')
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError('Choose a valid reporting period date (YYYY-MM-DD)') from None


def read_document(path,progress=None):
    notify=progress or (lambda event:None)
    notify(dict(phase='reading_json'))
    def reject_constant(value):
        raise ValueError(f'Invalid JSON number: {value}')
    doc=load_json(path,notify,reject_constant)
    if not isinstance(doc,dict):raise ValueError('JSON must contain a linelist document object')
    if doc.get('format_version') != 1:
        raise ValueError('Unsupported JSON format')
    if not re.fullmatch(r'[0-9a-f]{64}', doc.get('source_sha256', '')):
        raise ValueError('Missing or invalid source hash')
    for key in ('sheet', 'source_file'):
        if not isinstance(doc.get(key), str) or not doc[key]:
            raise ValueError(f'Missing {key}')
    headers = doc.get('headers')
    if not isinstance(headers, list) or not headers or any(not isinstance(h, str) or not h for h in headers) or len(set(headers)) != len(headers):
        raise ValueError('Invalid headers')
    if not isinstance(doc.get('records'), list):
        raise ValueError('Missing records')
    seen = set()
    total=len(doc['records'])
    notify(dict(phase='validating',processed=0,total=total))
    for number,record in enumerate(doc['records'],1):
        row = record.get('source_row')
        if type(row) is not int or row < 1 or row in seen:
            raise ValueError('Invalid or duplicate source row')
        seen.add(row)
        if not isinstance(record.get('data'), dict) or set(record['data']) != set(headers):
            raise ValueError(f'Invalid data keys at row {row}')
        if number%1000==0:notify(dict(phase='validating',processed=number,total=total))
    notify(dict(phase='validated',processed=total,total=total))
    return doc


def upload(path, schema='public', table='linelist_records', dry_run=False, connection=None, period=None,progress=None,document=None,create_schema=False):
    notify=progress or (lambda event:None)
    doc = document if document is not None else read_document(path,progress=notify)
    if dry_run:
        return len(doc['records'])
    from periods import parse_workflow_period,period_text,period_type,migrate_quarterly_periods
    period = parse_workflow_period(period,schema)
    snapshot_hash = doc['source_sha256']
    import_hash = hashlib.sha256(('linelist-period-v1:' + snapshot_hash + ':' + period_text(period)).encode()).hexdigest()
    import psycopg
    from psycopg import sql
    from psycopg.types.json import Jsonb
    # libpq reads PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD, PGSSLMODE.
    # Never print credentials or connection strings.
    if connection is None and not os.environ.get('PGHOST'):
        raise ValueError('Set PGHOST to the PostgreSQL server hostname or IP address')
    password = os.environ.get('PGPASSWORD')
    if connection is None and password is None:
        password = getpass.getpass('PostgreSQL password: ')
    target = sql.Identifier(schema, table)
    config = connection if connection is not None else dict(
        dbname=os.environ.get('PGDATABASE', 'ecews'),
        user=os.environ.get('PGUSER', 'postgres'), password=password)
    total=len(doc['records'])
    notify(dict(phase='connecting',processed=0,total=total,inserted=0,skipped=0))
    with psycopg.connect(**config, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            if create_schema:
                cur.execute(sql.SQL('CREATE SCHEMA IF NOT EXISTS {}').format(sql.Identifier(schema)))
            if schema=='quarterly':migrate_quarterly_periods(conn)
            cur.execute(sql.SQL('''CREATE TABLE IF NOT EXISTS {} (
                source_sha256 text NOT NULL,
                source_file text NOT NULL,
                sheet text NOT NULL,
                source_row integer NOT NULL,
                data jsonb NOT NULL,
                imported_at timestamptz NOT NULL DEFAULT now(),
                PRIMARY KEY (source_sha256, sheet, source_row)
            )''').format(target))
            cur.execute(sql.SQL('ALTER TABLE {} ADD COLUMN IF NOT EXISTS period {}, ADD COLUMN IF NOT EXISTS source_snapshot_sha256 text').format(target,sql.SQL(period_type(schema))))
            statement = sql.SQL('''INSERT INTO {} (source_sha256, source_file, sheet, source_row, data, period, source_snapshot_sha256)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_sha256, sheet, source_row) DO NOTHING''').format(target)
            inserted=0
            for start in range(0,total,500):
                batch=doc['records'][start:start+500]
                cur.executemany(statement, ((import_hash, doc['source_file'], doc['sheet'],
                                            r['source_row'], Jsonb(r['data']), period, snapshot_hash) for r in batch))
                inserted+=cur.rowcount
                processed=start+len(batch)
                notify(dict(phase='inserting',processed=processed,total=total,inserted=inserted,skipped=processed-inserted))
            notify(dict(phase='committing',processed=total,total=total,inserted=inserted,skipped=total-inserted))
    notify(dict(phase='completed',state='completed',processed=total,total=total,inserted=inserted,skipped=total-inserted))
    return inserted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--schema', default='public')
    parser.add_argument('--table', default='linelist_records')
    parser.add_argument('--dry-run', action='store_true', help='Validate JSON without connecting')
    parser.add_argument('--period', help='Reporting date YYYY-MM-DD (required for database upload)')
    args = parser.parse_args()
    count = upload(args.source, args.schema, args.table, args.dry_run, period=args.period)
    print(f'{"Validated" if args.dry_run else "Inserted"} {count:,} rows')


if __name__ == '__main__':
    main()
