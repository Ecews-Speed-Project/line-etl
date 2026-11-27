"""Aggregate HTS/TXNEW monitoring without exposing client-level records."""
import csv,io,re
from pathlib import Path
from fastapi import APIRouter,HTTPException,Request
router=APIRouter()
DATA=Path(__file__).parent/'.local_jobs'/'hts-monitoring.csv'
METRICS={'HTS_TST_POS':'hts_pos','TX_NEW total':'txnew','TX_NEW unique':'unique','Txnew Prints captured':'prints','Txnew No prints':'no_prints','TX_NEW non-unique':'non_unique'}
def is_summary_label(value):
    label=' '.join(re.sub(r'[^a-z0-9]+',' ',str(value or '').casefold()).split())
    return bool(re.match(r'^(?:total|subtotal|sub total|grand total|overall)(?: |$)',label)) or label in {'ecews','ecews total','ecews speed','speed total'}

def parse(data):
    if data.startswith(b'PK'):
        from openpyxl import load_workbook
        try:
            book=load_workbook(io.BytesIO(data),read_only=True,data_only=True)
            try:
                output=io.StringIO();writer=csv.writer(output)
                for index,row in enumerate(book.worksheets[0].iter_rows(values_only=True)):
                    if index>100000:raise ValueError('Excel monitoring files are limited to 100,000 rows.')
                    writer.writerow(['' if value is None else int(value) if isinstance(value,float) and value.is_integer() else value for value in row])
                data=output.getvalue().encode('utf-8')
            finally:book.close()
        except ValueError:raise
        except Exception:raise ValueError('Could not read the Excel workbook. Choose a valid .xlsx file.') from None
    try:text=data.decode('utf-8-sig')
    except UnicodeDecodeError:text=data.decode('cp1252')
    try:dialect=csv.Sniffer().sniff(text[:8192],delimiters=',\t;')
    except csv.Error:raise ValueError('Choose a comma- or tab-delimited monitoring CSV.')
    reader=csv.DictReader(io.StringIO(text),dialect=dialect)
    reader.fieldnames=[str(h).strip() for h in (reader.fieldnames or [])]
    normalize=lambda value:' '.join(value.casefold().replace('_',' ').replace('-',' ').split())
    aliases={'Txnew No prints':['No Print','No Prints','Txnew No prints'],
             'Txnew Prints captured':['Print capture','Prints captured','Txnew Prints captured'],
             'TX_NEW non-unique':['Non unique TX_NEW','TX_NEW non-unique']}
    source_columns={}
    for target,names in aliases.items():
        for name in names:
            matches=[h for h in reader.fieldnames if normalize(h)==normalize(name)]
            if len(matches)>1:raise ValueError('Ambiguous duplicate column: '+name)
            if matches:source_columns[target]=matches[0];break
    required={'State','LGA','Facility','HTS_TST_POS','TX_NEW total','TX_NEW unique'}
    if not required.issubset(reader.fieldnames):raise ValueError('Missing columns: '+', '.join(sorted(required-set(reader.fieldnames))))
    facilities={}
    excluded_summary_rows=0
    for line,row in enumerate(reader,2):
        if not any(str(v or '').strip() for v in row.values()):continue
        if None in row:raise ValueError(f'Extra cells on row {line}.')
        if any(is_summary_label(row.get(k)) for k in ('State','LGA','Facility')):
            excluded_summary_rows+=1
            continue
        if row.get('State'):
            state_key=' '.join(row['State'].split()).casefold()
            row['State']={'delta':'Delta','ekiti':'Ekiti','osun':'Osun'}.get(state_key,row['State'].strip())
        identity=tuple((row.get(k) or '').strip() or 'Unknown' for k in ('State','LGA','Facility'))
        group=facilities.setdefault(identity,dict(state=identity[0],lga=identity[1],facility=identity[2],**{v:0 for v in METRICS.values()}))
        for heading,key in METRICS.items():
            value=(row.get(source_columns.get(heading,heading)) or '').strip().replace(',','')
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
        for key in METRICS.values():state[key]+=group[key]
        rates(group)
    for state in states.values():
        for key in METRICS.values():total[key]+=state[key]
    return dict(excluded_summary_rows=excluded_summary_rows,facilities=sorted(facilities.values(),key=lambda r:(r['state'],r['lga'],r['facility'])),states=[rates(g) for _,g in sorted(states.items())],total=rates(total))
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
        if len(data)>10*1024*1024:raise HTTPException(413,'Monitoring file must be 10 MB or smaller.')
    try:return parse(bytes(data))
    except (ValueError,csv.Error) as exc:raise HTTPException(400,str(exc)) from None

@router.post('/api/hts-monitoring/word')
async def word_report(request:Request):
    import json
    from fastapi.responses import Response
    data=bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data)>10*1024*1024:raise HTTPException(413,'Report data must be 10 MB or smaller.')
    try:
        body=json.loads(data);rows=body['facilities']
        if not isinstance(rows,list) or not rows or len(rows)>100000:raise ValueError('Choose a processed monitoring dataset.')
        output=io.StringIO();writer=csv.writer(output);writer.writerow(['State','LGA','Facility',*METRICS])
        for row in rows:writer.writerow([row['state'],row['lga'],row['facility'],*[row.get(key,0) for key in METRICS.values()]])
        report=parse(output.getvalue().encode('utf-8'))
        source=str(body.get('source','Processed monitoring dataset'))[:240]
    except (ValueError,KeyError,TypeError,csv.Error) as exc:
        raise HTTPException(400,'Invalid monitoring report data: '+str(exc)) from None
    from hts_word_report import build
    return Response(build(report,source),media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',headers={'Content-Disposition':'attachment; filename="ECEWS_HTS_TXNEW_Report.docx"'})
