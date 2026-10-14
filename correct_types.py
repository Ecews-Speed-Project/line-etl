"""Validate and atomically save corrections to source JSONB and flat records."""
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from column_types import TYPES
from flatten_json import HEADERS


def ensure_audit(conn, schema):
    conn.execute(sql.SQL('ALTER TABLE {} ADD COLUMN IF NOT EXISTS corrected_value text, ADD COLUMN IF NOT EXISTS resolved_at timestamptz').format(
        sql.Identifier(schema, 'linelist_flat_type_errors')))


def correct(connection, schema, source_table, source_sha256, sheet, source_row, heading, value):
    if heading not in TYPES or TYPES[heading] == 'text':
        raise ValueError('Select a flagged date or numeric column')
    with psycopg.connect(**connection, connect_timeout=10) as conn:
        conn.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (schema+'.linelist_flat',))
        ensure_audit(conn, schema)
        errors = sql.Identifier(schema, 'linelist_flat_type_errors')
        source = sql.Identifier(schema, source_table)
        flat = sql.Identifier(schema, 'linelist_flat')
        safe = sql.Identifier(schema, 'linelist_safe_cast')
        key = (source_table, source_sha256, sheet, source_row, heading)
        error = conn.execute(sql.SQL('''SELECT resolved_at FROM {} WHERE source_table=%s AND source_sha256=%s
            AND sheet=%s AND source_row=%s AND heading=%s FOR UPDATE''').format(errors), key).fetchone()
        if error is None:
            raise ValueError('Error record not found')
        if error[0] is not None:
            raise ValueError('This error is already resolved; refresh the review')
        converted = conn.execute(sql.SQL('SELECT {}(%s,%s)').format(safe), (value,TYPES[heading])).fetchone()[0]
        if converted is None:
            raise ValueError('Enter a valid '+TYPES[heading]+' value; dates must use YYYY-MM-DD')
        record = conn.execute(sql.SQL('''SELECT data,period FROM {} WHERE source_sha256=%s AND sheet=%s
            AND source_row=%s FOR UPDATE''').format(source), (source_sha256,sheet,source_row)).fetchone()
        if record is None:
            raise ValueError('Source record not found')
        original,period = record
        text_defs = sql.SQL(', ').join(sql.SQL('{} text').format(sql.Identifier(h)) for h in HEADERS)
        expected_values = sql.SQL(', ').join(
            sql.SQL('j.{} AS {}').format(sql.Identifier(h),sql.Identifier(h)) if TYPES[h]=='text' else
            sql.SQL('{}(j.{},{})::{} AS {}').format(safe,sql.Identifier(h),sql.Literal(TYPES[h]),sql.SQL(TYPES[h]),sql.Identifier(h)) for h in HEADERS)
        predicates = sql.SQL(' AND ').join(sql.SQL('f.{} IS NOT DISTINCT FROM e.{}').format(sql.Identifier(h),sql.Identifier(h)) for h in HEADERS)
        rows = conn.execute(sql.SQL('''WITH expected AS MATERIALIZED (
            SELECT {} FROM jsonb_to_record(%s) AS j({})
        ) SELECT f.ctid FROM {} f CROSS JOIN expected e
          WHERE f.period IS NOT DISTINCT FROM %s::date AND {} LIMIT 2 FOR UPDATE OF f''').format(
            expected_values,text_defs,flat,predicates), (Jsonb(original),period)).fetchall()
        if len(rows)!=1:
            raise ValueError('Cannot identify exactly one matching flat row. No changes saved; check duplicate snapshots or changed data.')
        conn.execute(sql.SQL('UPDATE {} SET {}=%s::{} WHERE ctid=%s::tid').format(flat,sql.Identifier(heading),sql.SQL(TYPES[heading])), (converted,rows[0][0]))
        conn.execute(sql.SQL('''UPDATE {} SET data=jsonb_set(data,ARRAY[%s],to_jsonb(%s::{}),false)
            WHERE source_sha256=%s AND sheet=%s AND source_row=%s''').format(source,sql.SQL(TYPES[heading])),
            (heading,converted,source_sha256,sheet,source_row))
        conn.execute(sql.SQL('''UPDATE {} SET corrected_value=%s,resolved_at=now()
            WHERE source_table=%s AND source_sha256=%s AND sheet=%s AND source_row=%s AND heading=%s''').format(errors),
            (converted,)+key)
    return dict(saved=True, heading=heading, value=converted)
