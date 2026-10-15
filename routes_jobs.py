import json
import anyio
import shutil
import conversion_jobs
from fastapi import APIRouter,HTTPException,Request
from fastapi.responses import FileResponse
from conversion_jobs import create,status,folder,publish,begin_upload,enqueue,JOB_ROOT,JOBS,LOCK
import web_common

router=APIRouter()


@router.post('/api/conversions')
async def create_job(request:Request):
    try:
        body=await request.json()
        return create(body.get('filename',''),body.get('sheet',''),body.get('header_row',1))
    except (ValueError,AttributeError) as exc:
        raise HTTPException(400,str(exc)) from None


@router.put('/api/conversions/{job_id}/file')
async def upload_job(job_id:str,request:Request):
    claimed=False
    try:
        job=status(job_id)
        begin_upload(job_id)
        claimed=True
        received=0
        part=folder(job_id)/'upload.part'
        async with await anyio.open_file(part,'wb') as output:
            async for chunk in request.stream():
                received+=len(chunk)
                if received>web_common.MAX_SIZE:
                    raise ValueError('Upload exceeds the configured file-size limit')
                await output.write(chunk)
                publish(job_id,bytes_received=received)
        if not received:
            raise ValueError('The uploaded workbook is empty')
        part.replace(folder(job_id)/job['filename'])
        enqueue(job_id)
        return status(job_id)
    except Exception as exc:
        try:
            if not claimed:raise ValueError('Upload was not started')
            (folder(job_id)/'upload.part').unlink(missing_ok=True)
            publish(job_id,state='failed',phase='failed',error=str(exc) if isinstance(exc,ValueError) else 'Upload interrupted; please try again.')
        except (ValueError,KeyError):
            pass
        raise HTTPException(400,str(exc) if isinstance(exc,ValueError) else 'Upload failed') from None


@router.get('/api/conversions/{job_id}')
def job_status(job_id:str):
    try:return status(job_id)
    except ValueError as exc:raise HTTPException(404,str(exc)) from None


@router.get('/api/conversions/{job_id}/download')
def download(job_id:str,compressed:bool=False):
    job=job_status(job_id)
    if job['state']!='completed':raise HTTPException(409,'Conversion is not complete')
    filename='linelist.json.gz' if compressed else 'linelist.json'
    if not (folder(job_id)/filename).exists():raise HTTPException(404,'Compressed download is not available for this older job; convert again or download the plain JSON')
    return FileResponse(folder(job_id)/filename,media_type='application/gzip' if compressed else 'application/json',filename=filename)


@router.get('/api/conversions/{job_id}/errors')
def errors(job_id:str,offset:int=0,limit:int=100):
    job=job_status(job_id)
    if job['state']!='completed':raise HTTPException(409,'Conversion is not complete')
    if offset<0 or not 1<=limit<=200:raise HTTPException(400,'Invalid review page')
    report=json.loads((folder(job_id)/'cell_errors.json').read_text(encoding='utf-8'))
    return dict(total=report['flagged_cells'],issues=report['issues'][offset:offset+limit],offset=offset,limit=limit,note=report['note'])


@router.delete('/api/conversions/{job_id}')
def remove_job(job_id:str):
    with LOCK:
        job=job_status(job_id)
        if job['state'] not in ('completed','failed','created'):
            raise HTTPException(409,'Wait for this job to finish before removing its files')
        target=folder(job_id).resolve()
        if target.parent!=conversion_jobs.JOB_ROOT.resolve():raise HTTPException(400,'Invalid job directory')
        shutil.rmtree(target)
        JOBS.pop(job_id,None)
    return {'removed':True}
