"""Read-only upload and flattening summary by source snapshot and period."""
import psycopg
from psycopg import sql
from upload_json import parse_period


def summary(connection,schema='public',source_table='linelist_records',period=None):
    selected=parse_period(period) if period else None
    with psycopg.connect(**connection,connect_timeout=10) as conn:
        source=sql.Identifier(schema,source_table)
        exists=conn.execute('SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema=%s AND table_name=%s)',(schema,'linelist_flat_imports')).fetchone()[0]
        join=sql.SQL('LEFT JOIN {} t ON t.source_table=%s AND t.source_sha256=s.source_sha256 AND t.sheet=s.sheet AND t.source_row=s.source_row').format(sql.Identifier(schema,'linelist_flat_imports')) if exists else sql.SQL('')
        copied=sql.SQL('count(t.source_row)') if exists else sql.SQL('0::bigint')
        where=sql.SQL('WHERE s.period=%s') if selected else sql.SQL('')
        params=((source_table,) if exists else ())+((selected,) if selected else ())
        rows=conn.execute(sql.SQL('''SELECT s.source_sha256,s.source_file,s.sheet,s.period,count(*),{},
            count(*) FILTER (WHERE lower(btrim(s.data->>'CurrentARTStatus'))='active'),
            max(s.imported_at) FROM {} s {} {} GROUP BY s.source_sha256,s.source_file,s.sheet,s.period
            ORDER BY s.period DESC NULLS LAST,max(s.imported_at) DESC''').format(copied,source,join,where),params).fetchall()
    snapshots=[]
    periods={}
    for fingerprint,file,sheet,period,rows,flattened,active,uploaded in rows:
        state='Flattened' if flattened==rows else 'Partly flattened' if flattened else 'Not flattened'
        snapshot=dict(id=fingerprint,file=file,sheet=sheet,period=period.isoformat() if period else None,
                      rows=rows,flattened=flattened,pending=rows-flattened,active=active,status=state,
                      last_upload=uploaded.isoformat())
        snapshots.append(snapshot)
        group=periods.setdefault(snapshot['period'],dict(period=snapshot['period'],linelists=0,rows=0,flattened=0,pending=0,active=0))
        group['linelists']+=1
        for field in ['rows','flattened','pending','active']:group[field]+=snapshot[field]
    totals={field:sum(s[field] for s in snapshots) for field in ['rows','flattened','pending','active']}
    totals['linelists']=len(snapshots)
    return dict(linelists=snapshots,periods=list(periods.values()),totals=totals,
                active_definition="CurrentARTStatus = Active (case and surrounding spaces ignored). Counts are source rows, not patients deduplicated across periods.")
