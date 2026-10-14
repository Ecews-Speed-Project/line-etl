from pathlib import Path
import json
import tempfile
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from web_common import save_upload
router = APIRouter()
from header_mapping import inspect_headers, propose, standardize


@router.post('/api/headers')
def review_headers(file: UploadFile = File(...), sheet: str = Form(''), header_row: int = Form(1)):
    try:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'source.xlsx'
            save_upload(file, path)
            return propose(inspect_headers(path, sheet or None, header_row))
    except Exception as exc:
        raise HTTPException(400, str(exc) if isinstance(exc, (ValueError, KeyError)) else 'Could not read workbook headings') from None
    finally:
        file.file.close()


@router.post('/api/standardize')
def standardize_excel(file: UploadFile = File(...), mapping: str = Form(...),
                      sheet: str = Form(''), header_row: int = Form(1), allow_missing: bool = Form(False)):
    temporary = tempfile.TemporaryDirectory(prefix='linelist_map_')
    try:
        folder = Path(temporary.name)
        source = folder / Path((file.filename or 'source.xlsx').replace('\\', '/')).name
        if source.suffix.lower() != '.xlsx':
            raise ValueError('Choose an .xlsx workbook')
        save_upload(file, source)
        result = standardize(source, folder, json.loads(mapping), sheet or None, header_row, allow_missing)
        return FileResponse(result, media_type='application/zip', filename='converted_linelist.zip',
                            background=BackgroundTask(temporary.cleanup))
    except Exception as exc:
        temporary.cleanup()
        raise HTTPException(400, str(exc) if isinstance(exc, (ValueError, KeyError)) else 'Conversion failed. Check the workbook values.') from None
    finally:
        file.file.close()
