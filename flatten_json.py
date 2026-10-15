"""Materialize JSONB records into the 121-column linelist_flat table."""
import json
from pathlib import Path
from psycopg import sql
import psycopg
from column_types import TYPES, SAFE_CAST_BODY

HEADERS = json.loads((Path(__file__).parent / 'current_headers.json').read_text(encoding='utf-8'))
FLAT_HEADERS = HEADERS + ['period']
FLAT_TYPES = dict(TYPES, period='date')


def flatten(connection, schema='public', source_table='linelist_records',progress=None):
    notify=progress or (lambda event:None)
    notify(dict(phase='connecting'))
    if source_table in ('linelist_flat', 'linelist_flat_imports'):
        raise ValueError('Choose the JSONB source table, not a flat output table')
    target = sql.Identifier(schema, 'linelist_flat')
    tracking = sql.Identifier(schema, 'linelist_flat_imports')
    source = sql.Identifier(schema, source_table)
    safe = sql.Identifier(schema, 'linelist_safe_cast')
    errors = sql.Identifier(schema, 'linelist_flat_type_errors')
    with psycopg.connect(**connection, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            notify(dict(phase='waiting_for_database'))
            cur.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (schema + '.linelist_flat',))
            cur.execute(sql.SQL('CREATE OR REPLACE FUNCTION {}(val text,kind text) RETURNS text LANGUAGE plpgsql IMMUTABLE AS {}').format(safe, sql.Literal(SAFE_CAST_BODY)))
            definitions = sql.SQL(', ').join(sql.SQL('{} {}').format(sql.Identifier(h), sql.SQL(TYPES[h])) for h in HEADERS)
            text_definitions = sql.SQL(', ').join(sql.SQL('{} text').format(sql.Identifier(h)) for h in HEADERS)
            cur.execute(sql.SQL('CREATE TABLE IF NOT EXISTS {} ({})').format(target, definitions))
            cur.execute(sql.SQL('ALTER TABLE {} ADD COLUMN IF NOT EXISTS period date').format(target))
            cur.execute(sql.SQL('ALTER TABLE {} ADD COLUMN IF NOT EXISTS period date, ADD COLUMN IF NOT EXISTS source_snapshot_sha256 text').format(source))
            cur.execute(sql.SQL('CREATE INDEX IF NOT EXISTS {} ON {} (period)').format(sql.Identifier('linelist_flat_period_idx'), target))
            cur.execute('''SELECT column_name, data_type FROM information_schema.columns
                           WHERE table_schema=%s AND table_name='linelist_flat' ORDER BY ordinal_position''', (schema,))
            all_columns = cur.fetchall()
            if dict(all_columns).get('period') != 'date':
                raise ValueError('The period column must use DATE')
            existing = [(h,t) for h,t in all_columns if h != 'period']
            migrated = existing == [(h, 'text') for h in HEADERS]
            if migrated:
                notify(dict(phase='migrating_types'))
                backup = sql.Identifier(schema, 'linelist_flat_text_backup')
                cur.execute(sql.SQL('CREATE TABLE IF NOT EXISTS {} AS TABLE {}').format(backup, target))
                changes = sql.SQL(', ').join(sql.SQL('ALTER COLUMN {} TYPE {} USING {}({}, {})::{}').format(
                    sql.Identifier(h), sql.SQL(TYPES[h]), safe, sql.Identifier(h), sql.Literal(TYPES[h]), sql.SQL(TYPES[h]))
                    for h in HEADERS if TYPES[h] != 'text')
                cur.execute(sql.SQL('ALTER TABLE {} {}').format(target, changes))
            elif existing == [(h, 'timestamp without time zone' if h in ('Date_Generated', 'PBSDateCreated', 'RecapturedDate') else TYPES[h]) for h in HEADERS]:
                changes = sql.SQL(', ').join(sql.SQL('ALTER COLUMN {} TYPE date USING {}::date').format(
                    sql.Identifier(h), sql.Identifier(h)) for h in ('Date_Generated', 'PBSDateCreated', 'RecapturedDate'))
                cur.execute(sql.SQL('ALTER TABLE {} {}').format(target, changes))
            elif existing != [(h, TYPES[h]) for h in HEADERS]:
                raise ValueError('Existing linelist_flat has a different schema; it was not modified')
            cur.execute(sql.SQL('''CREATE TABLE IF NOT EXISTS {} (
                source_table text NOT NULL, source_sha256 text NOT NULL, sheet text NOT NULL,
                source_row integer NOT NULL, heading text NOT NULL, original_value text,
                expected_type text NOT NULL, reason text NOT NULL,
                PRIMARY KEY(source_table,source_sha256,sheet,source_row,heading))''').format(errors))
            cur.execute(sql.SQL('''CREATE TABLE IF NOT EXISTS {} (
                source_table text NOT NULL, source_sha256 text NOT NULL,
                sheet text NOT NULL, source_row integer NOT NULL,
                PRIMARY KEY(source_table, source_sha256, sheet, source_row))''').format(tracking))
            notify(dict(phase='checking_copied_rows'))
            cur.execute(sql.SQL('''CREATE TEMP TABLE linelist_operation_rows ON COMMIT DROP AS
                SELECT s.source_sha256,s.sheet,s.source_row,(t.source_row IS NOT NULL) AS copied
                FROM {} s LEFT JOIN {} t ON t.source_table=%s AND t.source_sha256=s.source_sha256
                AND t.sheet=s.sheet AND t.source_row=s.source_row''').format(source,tracking),(source_table,))
            cur.execute('SELECT count(*),count(*) FILTER(WHERE copied) FROM pg_temp.linelist_operation_rows')
            source_total,skipped=cur.fetchone()
            cur.execute('''CREATE TEMP TABLE linelist_pending_rows ON COMMIT DROP AS
                SELECT source_sha256,sheet,source_row,row_number() OVER () AS sequence
                FROM pg_temp.linelist_operation_rows WHERE NOT copied''')
            cur.execute('CREATE INDEX ON pg_temp.linelist_pending_rows(sequence)')
            pending_total=source_total-skipped
            notify(dict(phase='flattening',processed=skipped,total=source_total,inserted=0,skipped=skipped))
            columns = sql.SQL(', ').join(sql.Identifier(h) for h in HEADERS)
            # The posted Markdown escapes one underscore; Excel's actual heading is used.
            values = sql.SQL(', ').join(sql.SQL('j.{}').format(sql.Identifier(h)) if TYPES[h]=='text' else
                sql.SQL('{}(j.{}, {})::{}').format(safe, sql.Identifier(h), sql.Literal(TYPES[h]), sql.SQL(TYPES[h])) for h in HEADERS)
            query = sql.SQL('''WITH pending AS MATERIALIZED (
                SELECT s.* FROM {} s JOIN {} t ON t.source_sha256=s.source_sha256
                    AND t.sheet=s.sheet AND t.source_row=s.source_row WHERE t.sequence>%s AND t.sequence<=%s
            ), inserted AS (
                INSERT INTO {} ({}, period) SELECT {}, p.period FROM pending p
                CROSS JOIN LATERAL jsonb_to_record(p.data) AS j({}) RETURNING 1
            ), tracked AS (
                INSERT INTO {} (source_table,source_sha256,sheet,source_row)
                SELECT %s,source_sha256,sheet,source_row FROM pending RETURNING 1
            ) SELECT (SELECT count(*) FROM inserted), (SELECT count(*) FROM tracked)''').format(
                source, sql.Identifier('pg_temp','linelist_pending_rows'), target, columns, values, text_definitions, tracking)
            typed = [h for h in HEADERS if TYPES[h] != 'text']
            names_array = sql.SQL('ARRAY[{}]').format(sql.SQL(',').join(sql.Literal(h) for h in typed))
            values_array = sql.SQL('ARRAY[{}]').format(sql.SQL(',').join(sql.SQL('j.{}').format(sql.Identifier(h)) for h in typed))
            kinds_array = sql.SQL('ARRAY[{}]').format(sql.SQL(',').join(sql.Literal(TYPES[h]) for h in typed))
            pending_filter = sql.SQL('TRUE') if migrated else sql.SQL('''NOT EXISTS (
                SELECT 1 FROM {} t WHERE t.source_table=%s AND t.source_sha256=s.source_sha256
                AND t.sheet=s.sheet AND t.source_row=s.source_row)
                AND EXISTS (SELECT 1 FROM pg_temp.linelist_pending_rows b WHERE b.source_sha256=s.source_sha256
                AND b.sheet=s.sheet AND b.source_row=s.source_row AND b.sequence>%s AND b.sequence<=%s)''').format(tracking)
            issue_query = sql.SQL('''INSERT INTO {} (source_table,source_sha256,sheet,source_row,heading,original_value,expected_type,reason)
                SELECT %s,s.source_sha256,s.sheet,s.source_row,e.heading,e.value,e.kind,
                'Value cannot be safely converted; stored as NULL'
                FROM {} s CROSS JOIN LATERAL jsonb_to_record(s.data) AS j({})
                CROSS JOIN LATERAL unnest({}, {}, {}) AS e(heading,value,kind)
                WHERE ({}) AND e.value IS NOT NULL AND btrim(e.value)<>'' AND {}(e.value,e.kind) IS NULL
                ON CONFLICT DO NOTHING''').format(errors, source, text_definitions, names_array, values_array,
                                                 kinds_array, pending_filter, safe)
            if migrated:
                notify(dict(phase='checking_type_errors'))
                cur.execute(issue_query,(source_table,))
            inserted=0
            for start in range(0,pending_total,2000):
                end=min(start+2000,pending_total)
                if not migrated:
                    cur.execute(issue_query,(source_table,source_table,start,end))
                cur.execute(query,(start,end,source_table))
                copied,tracked=cur.fetchone()
                if copied!=tracked:raise ValueError('Flattening row reconciliation failed')
                inserted+=copied
                notify(dict(phase='flattening',processed=skipped+end,total=source_total,inserted=inserted,skipped=skipped))
            notify(dict(phase='committing',processed=source_total,total=source_total,inserted=inserted,skipped=skipped))
            cur.execute(sql.SQL('SELECT count(*) FROM {}').format(target))
            total = cur.fetchone()[0]
            from correct_types import ensure_audit
            ensure_audit(conn,schema)
            cur.execute(sql.SQL('SELECT count(*) FROM {} WHERE resolved_at IS NULL').format(errors))
            flagged = cur.fetchone()[0]
    notify(dict(state='completed',phase='completed',processed=source_total,total=source_total,inserted=inserted,skipped=skipped))
    return dict(inserted=inserted, total=total, columns=FLAT_HEADERS, types=FLAT_TYPES,
                migrated=migrated, flagged=flagged, table=schema + '.linelist_flat')


def browse(connection, schema='public', offset=0, limit=25, period=None):
    if offset < 0 or not 1 <= limit <= 100:
        raise ValueError('Invalid page size or offset')
    with psycopg.connect(**connection, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            target = sql.Identifier(schema, 'linelist_flat')
            from upload_json import parse_period
            selected_period = parse_period(period) if period else None
            where = sql.SQL('WHERE period=%s') if selected_period else sql.SQL('')
            parameters = (selected_period,) if selected_period else ()
            cur.execute(sql.SQL('SELECT count(*) FROM {} {}').format(target, where), parameters)
            total = cur.fetchone()[0]
            cur.execute(sql.SQL('SELECT {} FROM {} {} ORDER BY ctid LIMIT %s OFFSET %s').format(
                sql.SQL(', ').join(sql.Identifier(h) for h in FLAT_HEADERS), target, where), parameters + (limit, offset))
            rows = [[str(v) if v is not None else None for v in row] for row in cur.fetchall()]
    return dict(columns=FLAT_HEADERS, types=FLAT_TYPES, rows=rows, total=total, offset=offset, limit=limit)


def type_errors(connection, schema='public', offset=0, limit=25):
    if offset < 0 or not 1 <= limit <= 100:
        raise ValueError('Invalid page size or offset')
    with psycopg.connect(**connection, connect_timeout=10) as conn:
        from correct_types import ensure_audit
        ensure_audit(conn,schema)
        target = sql.Identifier(schema, 'linelist_flat_type_errors')
        total = conn.execute(sql.SQL('SELECT count(*) FROM {} WHERE resolved_at IS NULL').format(target)).fetchone()[0]
        rows = conn.execute(sql.SQL('''SELECT sheet,source_row,heading,original_value,expected_type,reason
            FROM {} WHERE resolved_at IS NULL ORDER BY source_sha256,sheet,source_row,heading LIMIT %s OFFSET %s''').format(target), (limit,offset)).fetchall()
        keys = conn.execute(sql.SQL('''SELECT source_table,source_sha256,sheet,source_row,heading,expected_type
            FROM {} WHERE resolved_at IS NULL ORDER BY source_sha256,sheet,source_row,heading LIMIT %s OFFSET %s''').format(target), (limit,offset)).fetchall()
    return dict(columns=['Sheet','Source row','Heading','Original value','Expected type','Reason'],
                rows=rows,total=total,offset=offset,limit=limit,
                errors=[dict(zip(['source_table','source_sha256','sheet','source_row','heading','expected_type'],key)) for key in keys])
