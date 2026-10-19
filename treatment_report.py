"""Reproducible treatment and viral-load indicators for one uploaded snapshot."""
from datetime import date,datetime
from decimal import Decimal,InvalidOperation
import re
import psycopg
from psycopg import sql
from upload_json import parse_period
from periods import period_text

AGE_BANDS=['Less than 1','1-4yrs','5-9yrs','10-14yrs','15-19yrs']
COUNTS=['txcurr','eligible','sample_collected','result','vl_suppression','undetectable','llv','unsuppressed']
LABELS={'txcurr':'TxCurr','eligible':'Eligible','sample_collected':'Sample collected','result':'Result',
        'vl_suppression':'VL suppression','undetectable':'Undetectable','llv':'LLV','unsuppressed':'Unsuppressed',
        'coverage':'Coverage','suppression_rate':'Suppression rate','undetectable_rate':'Undetectable rate','llv_rate':'LLV rate'}
FIELDS=['CurrentARTStatus','DaysOfARVRefill','LastDateOfSampleCollection','DateofCurrentViralLoad','CurrentViralLoad','Current_Age','State']


def number(value):
    try:
        text=str(value).strip()
        if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',text):return None
        result=Decimal(text)
        return result if result.is_finite() else None
    except (InvalidOperation,ValueError,TypeError):return None


def calendar_date(value):
    if value is None:return None
    text=str(value).strip()
    try:
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}',text):return date.fromisoformat(text)
        if re.match(r'^\d{4}-\d{2}-\d{2}[T ]',text):return datetime.fromisoformat(text.replace('Z','+00:00')).date()
        return None
    except ValueError:return None


def window(end_date):
    end=parse_period(end_date)
    try:start=end.replace(year=end.year-1)
    except ValueError:start=end.replace(year=end.year-1,day=28)
    return start,end


def aggregate(rows,end_date,progress=None,total=None):
    start,end=window(end_date)
    groups={name:{key:0 for key in COUNTS} for name in ['all','paediatrics','adults','unknown_age']}
    quality=dict(active_missing_refill=0,eligible_invalid_sample_date=0,eligible_invalid_result_date=0,
                 eligible_missing_or_invalid_vl=0,active_unknown_age=0)
    states={}
    paediatric_states={}
    scanned=0
    for row in rows:
        status,refill,sample_date,result_date,viral_load,age=row[:6]
        state=str(row[6] or "Unknown state").strip().capitalize() if len(row)>6 else "Unknown state"
        state=state or "Unknown state"
        if state not in states:states[state]={key:0 for key in COUNTS}
        if state not in paediatric_states:
            paediatric_states[state]={'total':{key:0 for key in COUNTS},'bands':{band:{key:0 for key in COUNTS} for band in AGE_BANDS}}
        scanned+=1
        if progress and scanned%2000==0:progress(dict(phase='reporting',processed=scanned,total=total))
        if str(status or '').strip().casefold()!='active':continue
        age=number(age)
        cohort='paediatrics' if age is not None and 0<=age<20 else 'adults' if age is not None and age>=20 else 'unknown_age'
        if cohort=='unknown_age':quality['active_unknown_age']+=1
        selected=[groups['all'],groups[cohort],states[state]]
        if cohort=='paediatrics':
            band=AGE_BANDS[0 if age<1 else 1 if age<5 else 2 if age<10 else 3 if age<15 else 4]
            selected.extend([paediatric_states[state]['total'],paediatric_states[state]['bands'][band]])
        for group in selected:group['txcurr']+=1
        refill=number(refill)
        if refill is None:quality['active_missing_refill']+=1
        if refill is None or refill<180:continue
        for group in selected:group['eligible']+=1
        collected=calendar_date(sample_date);result_day=calendar_date(result_date);vl=number(viral_load)
        if collected is None:quality['eligible_invalid_sample_date']+=1
        if result_day is None:quality['eligible_invalid_result_date']+=1
        if vl is None or vl<0:quality['eligible_missing_or_invalid_vl']+=1
        for group in selected:
            if collected is not None and start<=collected<=end:group['sample_collected']+=1
            if result_day is None or not start<=result_day<=end or vl is None or vl<0:continue
            group['result']+=1
            if vl<1000:group['vl_suppression']+=1
            if vl<50:group['undetectable']+=1
            elif vl<1000:group['llv']+=1
    pediatric_groups=[g for state in paediatric_states.values() for g in [state['total'],*state['bands'].values()]]
    for group in list(groups.values())+list(states.values())+pediatric_groups:
        group['unsuppressed']=group['result']-group['vl_suppression']
        for name,numerator,denominator in [('sample_collection_rate','sample_collected','eligible'),('coverage','result','eligible'),('suppression_rate','vl_suppression','result'),
                                           ('undetectable_rate','undetectable','result'),('llv_rate','llv','result')]:
            group[name]=100*group[numerator]/group[denominator] if group[denominator] else None
    return dict(start_date=start.isoformat(),end_date=end.isoformat(),groups=groups,states=dict(sorted(states.items())),paediatric_states=dict(sorted(paediatric_states.items())),quality=quality,rows_scanned=scanned,
                definitions=["TxCurr: CurrentARTStatus equals Active, ignoring case and surrounding spaces.",
                 'Eligible: Active and DaysOfARVRefill >= 180. This uses refill days, not days on ART.',
                 'Sample collected: Eligible and LastDateOfSampleCollection within the inclusive reporting window.',
                 'Result: Eligible, DateofCurrentViralLoad in the window and a finite numeric CurrentViralLoad >= 0.',
                 'VL suppression: Result with CurrentViralLoad < 1000. Undetectable: Result with CurrentViralLoad < 50.',
                 'LLV: Result with 50 <= CurrentViralLoad < 1000 (50-999 for integer results). Unsuppressed = Result - VL suppression.',
                 'Sample collection rate = Sample collected / Eligible. Coverage = Result / Eligible. The other three rates use Result as their denominator. Rates are percentages; a zero denominator is N/A.',
                 'Paediatrics uses 0 <= Current_Age < 20; adults use Current_Age >= 20. Missing or invalid ages are reported separately.',
                 'Counts are rows within one selected snapshot. Status is taken from that snapshot; this does not reconstruct status at an earlier reporting date.'])


def calculate(connection,schema,source_table,snapshot_id,sheet,end_date,progress=None,activity_start_date=None,activity_end_date=None,comparison_snapshot_id='',comparison_sheet=''):
    window(end_date)
    if not re.fullmatch(r'[0-9a-f]{64}',snapshot_id):raise ValueError('Select a valid uploaded linelist')
    notify=progress or (lambda event:None)
    notify(dict(phase='connecting'))
    source=sql.Identifier(schema,source_table)
    with psycopg.connect(**connection,connect_timeout=10) as conn:
        context=conn.execute(sql.SQL('''SELECT source_file,period,count(*) FROM {} WHERE source_sha256=%s AND sheet=%s
            GROUP BY source_file,period''').format(source),(snapshot_id,sheet)).fetchall()
        if len(context)!=1:raise ValueError('Select exactly one existing linelist snapshot and sheet')
        filename,period,total=context[0]
        notify(dict(phase='reporting',processed=0,total=total))
        definitions=sql.SQL(',').join(sql.SQL('{} text').format(sql.Identifier(h)) for h in FIELDS)
        columns=sql.SQL(',').join(sql.SQL('j.{}').format(sql.Identifier(h)) for h in FIELDS)
        with conn.cursor(name='treatment_indicator_rows') as cursor:
            cursor.itersize=2000
            cursor.execute(sql.SQL('''SELECT {} FROM {} s CROSS JOIN LATERAL jsonb_to_record(s.data) AS j({})
                WHERE s.source_sha256=%s AND s.sheet=%s''').format(columns,source,definitions),(snapshot_id,sheet))
            report=aggregate(cursor,end_date,progress=notify,total=total)
        if activity_start_date is not None:
            from activity_indicators import calculate_activity
            report['activity']=calculate_activity(conn,schema,source_table,snapshot_id,sheet,activity_start_date,activity_end_date,comparison_snapshot_id,comparison_sheet,notify)
            report['definitions'].extend(report['activity']['definitions'])
    report['source']=dict(file=filename,period=period_text(period),sheet=sheet,snapshot_id=snapshot_id,rows=total)
    notify(dict(phase='completed',state='completed',processed=total,total=total))
    return report
