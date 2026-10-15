"""Disk-backed uploads and bounded background Excel conversion jobs."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import threading
import time
import uuid

from excel_to_json import convert
from web_common import ROOT

JOB_ROOT = Path(os.environ.get('LINELIST_JOB_DIR', str(ROOT/'.local_jobs')))
EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix='excel-converter')
LOCK = threading.RLock()
JOBS = {}


def folder(job_id):
    if len(job_id)!=32 or any(c not in '0123456789abcdef' for c in job_id):
        raise ValueError('Invalid conversion job')
    return JOB_ROOT/job_id


def publish(job_id, **event):
    with LOCK:
        job=JOBS[job_id]
        old_phase=job.get('phase')
        job.update(event)
        now=time.monotonic()
        if old_phase!=job.get('phase') or now-job.get('_saved',0)>.5 or job.get('state') in ('completed','failed'):
            job['_saved']=now
            snapshot={k:v for k,v in job.items() if not k.startswith('_')}
            temp=folder(job_id)/'status.tmp'
            temp.write_text(json.dumps(snapshot),encoding='utf-8')
            os.replace(temp,folder(job_id)/'status.json')


def create(filename,sheet='',header_row=1):
    name=Path(filename.replace('\\','/')).name
    if not name.lower().endswith('.xlsx') or len(name)>220:
        raise ValueError('Choose an .xlsx workbook')
    if type(header_row) is not int or header_row<1:
        raise ValueError('Header row must be positive')
    job_id=uuid.uuid4().hex
    folder(job_id).mkdir(parents=True)
    with LOCK:
        JOBS[job_id]=dict(id=job_id,filename=name,sheet=sheet,header_row=header_row,
                          state='created',phase='waiting_for_upload',bytes_received=0,records=0,processed=0)
    publish(job_id)
    return status(job_id)


def status(job_id):
    path=folder(job_id)
    with LOCK:
        if job_id in JOBS:
            return {k:v for k,v in JOBS[job_id].items() if not k.startswith('_')}
    if not (path/'status.json').exists():
        raise ValueError('Conversion job not found')
    result=json.loads((path/'status.json').read_text(encoding='utf-8'))
    if result['state'] not in ('completed','failed'):
        result.update(state='failed',phase='interrupted',error='The server restarted before this job finished. Upload the workbook again.')
    return result


def begin_upload(job_id):
    with LOCK:
        if job_id not in JOBS or JOBS[job_id]['state']!='created':
            raise ValueError('This job cannot accept another upload')
        publish(job_id,state='uploading',phase='uploading')


def run(job_id):
    try:
        job=status(job_id)
        report={}
        publish(job_id,state='converting',phase='hashing')
        count=convert(folder(job_id)/job['filename'],folder(job_id)/'linelist.json',
                      job['sheet'] or None,job['header_row'],report=report,
                      progress=lambda event:publish(job_id,**event))
        (folder(job_id)/'cell_errors.json').write_text(json.dumps(report,ensure_ascii=False),encoding='utf-8')
        publish(job_id,state='completed',phase='completed',records=count,flagged_cells=report['flagged_cells'])
    except Exception as exc:
        message=str(exc) if isinstance(exc,(ValueError,KeyError)) else 'Could not convert this workbook. Check its format and available disk space.'
        publish(job_id,state='failed',phase='failed',error=message)


def enqueue(job_id):
    publish(job_id,state='queued',phase='queued')
    EXECUTOR.submit(run,job_id)
