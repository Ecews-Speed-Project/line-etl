"""Aggregate HTS/TXNEW monitoring without exposing client-level records."""
import csv,io
from pathlib import Path
from fastapi import APIRouter,HTTPException,Request
router=APIRouter()
DATA=Path(__file__).parent/'.local_jobs'/'hts-monitoring.csv'
METRICS={'HTS_TST_POS':'hts_pos','TX_NEW total':'txnew','TX_NEW unique':'unique','Txnew Prints captured':'prints','Txnew No prints':'no_prints','TX_NEW non-unique':'non_unique'}
def parse(data):
    try:text=data.decode('utf-8-sig')
    except UnicodeDecodeError:text=data.decode('cp1252')
    try:dialect=csv.Sniffer().sniff(text[:8192],delimiters=',\t;')
    except csv.Error:raise ValueError('Choose a comma- or tab-delimited monitoring CSV.')
    reader=csv.DictReader(io.StringIO(text),dialect=dialect)
    reader.fieldnames=[str(h).strip() for h in (reader.fieldnames or [])]
    required={'State','LGA','Facility','HTS_TST_POS','TX_NEW total','TX_NEW unique'}
    if not required.issubset(reader.fieldnames):raise ValueError('Missing columns: '+', '.join(sorted(required-set(reader.fieldnames))))
    facilities={}
    for line,row in enumerate(reader,2):
        if not any(str(v or '').strip() for v in row.values()):continue
        if None in row:raise ValueError(f'Extra cells on row {line}.')
        identity=tuple((row.get(k) or '').strip() or 'Unknown' for k in ('State','LGA','Facility'))
        group=facilities.setdefault(identity,dict(state=identity[0],lga=identity[1],facility=identity[2],**{v:0 for v in METRICS.values()}))
        for heading,key in METRICS.items():
            value=(row.get(heading) or '').strip().replace(',','')
            if value and (not value.isascii() or not value.isdigit()):raise ValueError(f'{heading} must be a nonnegative whole number on row {line}.')
            group[key]+=int(value or 0)
    if not facilities:raise ValueError('The file contains no facility records.')
    states={};total={v:0 for v in METRICS.values()}
    def rates(g):
        g['linkage']=100*g['txnew']/g['hts_pos'] if g['hts_pos'] else None
        g['unique_linkage']=100*g['unique']/g['hts_pos'] if g['hts_pos'] else None
        return g
    for group in facilities.values():
        state=states.setdefault(group['state'],dict(state=group['state'],**{v:0 for v in METRICS.values()}))
        for key in METRICS.values():state[key]+=group[key];total[key]+=group[key]
        rates(group)
    return dict(facilities=sorted(facilities.values(),key=lambda r:(r['state'],r['lga'],r['facility'])),states=[rates(g) for _,g in sorted(states.items())],total=rates(total))
@router.get('/api/hts-monitoring')
def initial():
    if not DATA.exists():raise HTTPException(404,'Upload a monitoring CSV to begin.')
    try:return parse(DATA.read_bytes())
    except ValueError as exc:raise HTTPException(400,str(exc)) from None
@router.post('/api/hts-monitoring')
async def upload(request:Request):
    data=bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data)>10*1024*1024:raise HTTPException(413,'Monitoring CSV must be 10 MB or smaller.')
    try:return parse(bytes(data))
    except (ValueError,csv.Error) as exc:raise HTTPException(400,str(exc)) from None
