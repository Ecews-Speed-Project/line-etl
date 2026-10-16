"""Weekly dates and quarterly fiscal labels are separate period types."""
import re
from datetime import date
from psycopg import sql

def quarterly_period(value):
    value=str(value or '').strip().upper()
    if not re.fullmatch(r'FY\d{2}Q[1-4]',value):
        raise ValueError('Enter a quarterly period such as FY26Q1 or FY26Q4.')
    return value

def period_type(schema):return 'text' if schema=='quarterly' else 'date'

def parse_workflow_period(value,schema):
    if schema=='quarterly':return quarterly_period(value)
    from upload_json import parse_period
    return parse_period(value)

def period_text(value):return value.isoformat() if isinstance(value,date) else str(value) if value is not None else None

def quarter_end(value):
    try:label=quarterly_period(value)
    except ValueError:return period_text(value)
    year=2000+int(label[2:4]);quarter=int(label[-1])
    return [date(year-1,12,31),date(year,3,31),date(year,6,30),date(year,9,30)][quarter-1].isoformat()

def migrate_quarterly_periods(conn):
    # Preserve old values and row identities; only the quarterly column type changes.
    conn.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',('quarterly.linelist_flat',))
    for table in ['linelist_records','linelist_flat']:
        found=conn.execute('SELECT data_type FROM information_schema.columns WHERE table_schema=%s AND table_name=%s AND column_name=%s',('quarterly',table,'period')).fetchone()
        if found and found[0]=='date':
            conn.execute(sql.SQL('ALTER TABLE {} ALTER COLUMN period TYPE text USING period::text').format(sql.Identifier('quarterly',table)))
