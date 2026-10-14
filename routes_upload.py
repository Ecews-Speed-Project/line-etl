from pathlib import Path
import json
import tempfile
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from web_common import save_upload
router = APIRouter()
from upload_json import read_document, parse_period, upload


@router.post('/api/upload')
def upload_json(file: UploadFile = File(...), host: str = Form('localhost'),
                port: int = Form(5432), database: str = Form('ecews'),
                username: str = Form('postgres'), password: str = Form(...),
                schema: str = Form('public'), table: str = Form('linelist_records'),
                acknowledge_errors: bool = Form(False), period: str = Form(...)):
    if not (file.filename or '').lower().endswith('.json'):
        raise HTTPException(400, 'Choose the JSON produced by step 1')
    try:
        selected_period = parse_period(period)
        with tempfile.TemporaryDirectory(prefix='linelist_') as folder:
            source = Path(folder) / 'upload.json'
            save_upload(file, source)
            document = read_document(source)
            if document.get('conversion_report', {}).get('issues') and not acknowledge_errors:
                raise ValueError('Review the flagged cells and acknowledge them before uploading')
            del document
            total = upload(source, dry_run=True)
            inserted = upload(source, schema, table, connection=dict(
                host=host, port=port, dbname=database, user=username, password=password), period=selected_period)
            return dict(total=total, inserted=inserted, skipped=total-inserted, period=selected_period.isoformat())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except Exception:
        # Do not expose database credentials or patient values in browser errors.
        raise HTTPException(400, 'Upload failed. Check the JSON format, database connection, credentials and table permissions.') from None
    finally:
        file.file.close()


@router.post('/api/review-json')
def review_json(file: UploadFile = File(...), offset: int = Form(0), limit: int = Form(100)):
    try:
        if offset < 0 or not 1 <= limit <= 200:
            raise ValueError('Invalid review page')
        with tempfile.TemporaryDirectory(prefix='linelist_review_') as folder:
            path = Path(folder) / 'review.json'
            save_upload(file, path)
            doc = read_document(path)
            report = doc.get('conversion_report', {})
            issues = report.get('issues', [])
            if not isinstance(issues, list):
                raise ValueError('Invalid conversion report')
            return dict(total=len(issues), issues=issues[offset:offset+limit], offset=offset, limit=limit,
                        rows=len(doc['records']), note=report.get('note', 'This file has no conversion report.'))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    finally:
        file.file.close()
