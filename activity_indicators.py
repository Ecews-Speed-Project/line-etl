"""Quarter activity counts and conservative, disk-backed RTT client matching."""
from pathlib import Path
import sqlite3
import tempfile

KEYS=['txnew','transferred_in','death','rtt','stopped','transferred_out']
EVENT_FIELDS=['CurrentARTStatus','ARTStartDate','TI','Date_Transfered_In','Outcomes_Date','Current_Age','State','Datim_Code','FacilityName','PepID','patient_id']

def normalized(value):return ' '.join(str(value or '').strip().casefold().split())

def client_keys(row):
    facility=('code:'+normalized(row.get('Datim_Code'))) if normalized(row.get('Datim_Code')) else ('name:'+normalized(row.get('FacilityName'))) if normalized(row.get('FacilityName')) else None
    if not facility:return []
    return [(kind,facility,normalized(row.get(field))) for kind,field in [('pep','PepID'),('patient','patient_id')] if normalized(row.get(field))]

class MatchIndex:
    def __init__(self,path):
        self.db=sqlite3.connect(path)
        self.db.execute('CREATE TABLE identities (side text,kind text,facility text,identifier text,n integer,record_id integer,status text,PRIMARY KEY(side,kind,facility,identifier))')
    def add(self,side,row,record_id):
        for kind,facility,identifier in client_keys(row):
            self.db.execute('INSERT INTO identities VALUES (?,?,?,?,1,?,?) ON CONFLICT(side,kind,facility,identifier) DO UPDATE SET n=n+1', (side,kind,facility,identifier,record_id,normalized(row.get('CurrentARTStatus'))))
    def previous(self,row):
        found=[]
        for key in client_keys(row):
            current=self.db.execute('SELECT n FROM identities WHERE side=? AND kind=? AND facility=? AND identifier=?',('current',)+key).fetchone()
            previous=self.db.execute('SELECT n,record_id,status FROM identities WHERE side=? AND kind=? AND facility=? AND identifier=?',('previous',)+key).fetchone()
            if previous:
                if previous[0]!=1 or not current or current[0]!=1:return None,'ambiguous'
                found.append((previous[1],previous[2]))
        if not found:return None,'unmatched'
        if len({r[0] for r in found})!=1:return None,'ambiguous'
        return found[0][1],'matched'
    def close(self):self.db.close()

class ActivityCounts:
    def __init__(self,start,end,comparison=False):
        from upload_json import parse_period
        self.start=parse_period(start);self.end=parse_period(end)
        if self.start>self.end:raise ValueError('Activity start date must be on or before its end date.')
        self.comparison=comparison
        self.groups={name:self.empty() for name in ['all','paediatrics','adults','unknown_age']}
        self.states={};self.paediatric_states={}
        self.quality=dict(rtt_unmatched_active=0,rtt_ambiguous_active=0,invalid_art_dates=0,invalid_transfer_dates=0,invalid_outcome_dates=0)
    def empty(self):return {key:(None if key=='rtt' and not self.comparison else 0) for key in KEYS}
    def add(self,row,previous_status=None,match='unavailable'):
        from treatment_report import calendar_date,number
        status=normalized(row.get('CurrentARTStatus'));age=number(row.get('Current_Age'))
        cohort='paediatrics' if age is not None and 0<=age<20 else 'adults' if age is not None and age>=20 else 'unknown_age'
        state=str(row.get('State') or 'Unknown state').strip().capitalize() or 'Unknown state'
        self.states.setdefault(state,self.empty());self.paediatric_states.setdefault(state,self.empty())
        selected=[self.groups['all'],self.groups[cohort],self.states[state]]
        if cohort=='paediatrics':selected.append(self.paediatric_states[state])
        dates={key:calendar_date(row.get(field)) for key,field in [('art','ARTStartDate'),('transfer','Date_Transfered_In'),('outcome','Outcomes_Date')]}
        for key,field in [('art','ARTStartDate'),('transfer','Date_Transfered_In'),('outcome','Outcomes_Date')]:
            if row.get(field) is not None and str(row[field]).strip() and dates[key] is None:self.quality['invalid_'+key+'_dates']+=1
        inside=lambda key:dates[key] is not None and self.start<=dates[key]<=self.end
        hits=[]
        if inside('art') and normalized(row.get('TI'))!='yes':hits.append('txnew')
        if inside('transfer'):hits.append('transferred_in')
        if inside('outcome'):
            if status=='death':hits.append('death')
            if status=='discontinued care':hits.append('stopped')
            if status=='transferred out':hits.append('transferred_out')
        if self.comparison and status=='active':
            if match in ['ambiguous','unmatched']:self.quality['rtt_'+match+'_active']+=1
            if match=='matched' and normalized(previous_status) not in ['','active']:hits.append('rtt')
        for group in selected:
            for key in hits:group[key]+=1
    def result(self):
        return dict(start_date=self.start.isoformat(),end_date=self.end.isoformat(),groups=self.groups,states=self.states,paediatric_states=self.paediatric_states,quality=self.quality,
            definitions=[
             f'Activity window: {self.start.isoformat()} to {self.end.isoformat()}, inclusive. These counts do not require Active status or 180 refill days.',
             'TxNew: ARTStartDate in the activity window, excluding TI equal to YES (case and surrounding spaces ignored). Blank TI is included.',
             'Transferred in: Date_Transfered_In in the activity window, regardless of ART status or TI.',
             'Death: CurrentARTStatus = Death and Outcomes_Date in the activity window.',
             'Stopped: CurrentARTStatus = Discontinued care and Outcomes_Date in the activity window.',
             'Transferred out: CurrentARTStatus = Transferred out and Outcomes_Date in the activity window.',
             'RTT: matched previous status is neither Active nor blank, and current status is Active. No event-date filter is applied to RTT. With no selected quarterly comparison, RTT is N/A.',
             'RTT matches facility + PepID, with facility + patient_id fallback. Facility uses Datim_Code, or FacilityName when code is missing. Identifiers are trimmed and case-insensitive. Duplicate or conflicting matches are excluded and counted as ambiguous; unmatched current Active rows are reported separately.',
             'Age/state breakdowns use the current linelist. Counts are source rows, consistent with the existing report. IIT and IIT rate remain N/A until their definitions are supplied.'])

def activity_group(report,name='ECEWS',paediatric=False):
    activity=report.get('activity')
    if not activity:return {key:None for key in KEYS}
    if name=='ECEWS':return activity['groups']['paediatrics' if paediatric else 'all']
    return activity['paediatric_states' if paediatric else 'states'].get(name,{key:None for key in KEYS})

def calculate_activity(conn,schema,table,snapshot_id,sheet,start,end,comparison_id='',comparison_sheet='',progress=None):
    from psycopg import sql
    counts=ActivityCounts(start,end,bool(comparison_id));notify=progress or (lambda event:None)
    fields=sql.SQL(',').join(sql.SQL('s.data->>{}').format(sql.Literal(f)) for f in EVENT_FIELDS)
    def stream(schema,table,snapshot,sheet,name):
        with conn.cursor(name=name) as cursor:
            cursor.itersize=2000
            cursor.execute(sql.SQL('SELECT s.source_row,{} FROM {} s WHERE s.source_sha256=%s AND s.sheet=%s').format(fields,sql.Identifier(schema,table)),(snapshot,sheet))
            for record in cursor:yield record[0],dict(zip(EVENT_FIELDS,record[1:]))
    with tempfile.TemporaryDirectory(prefix='linelist_activity_') as folder:
        index=MatchIndex(str(Path(folder)/'matching.sqlite'))
        try:
            if comparison_id:
                notify(dict(phase='matching_previous',processed=0,total=None))
                for n,(row_id,row) in enumerate(stream('quarterly','linelist_records',comparison_id,comparison_sheet,'activity_previous'),1):
                    index.add('previous',row,row_id)
                    if n%2000==0:notify(dict(phase='matching_previous',processed=n,total=None))
                notify(dict(phase='matching_current',processed=0,total=None))
                for n,(row_id,row) in enumerate(stream(schema,table,snapshot_id,sheet,'activity_current_keys'),1):
                    index.add('current',row,row_id)
                    if n%2000==0:notify(dict(phase='matching_current',processed=n,total=None))
                index.db.commit()
            notify(dict(phase='activity_indicators',processed=0,total=None))
            for n,(row_id,row) in enumerate(stream(schema,table,snapshot_id,sheet,'activity_events'),1):
                previous,match=index.previous(row) if comparison_id and normalized(row.get('CurrentARTStatus'))=='active' else (None,'unavailable')
                counts.add(row,previous,match)
                if n%2000==0:notify(dict(phase='activity_indicators',processed=n,total=None))
        finally:index.close()
    return counts.result()
