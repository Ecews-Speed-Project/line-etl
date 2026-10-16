from pathlib import Path
import json
import tempfile
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from web_common import save_upload
router = APIRouter()
from header_mapping import inspect_headers, propose, standardize
from operation_progress import callback


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
                      sheet: str = Form(''), header_row: int = Form(1), allow_missing: bool = Form(False),
                      include_excel:bool=Form(True),progress_id:str=Form('')):
    temporary = tempfile.TemporaryDirectory(prefix='linelist_map_')
    notify=lambda event:None
    try:
        notify=callback(progress_id,'standardize')
        notify(dict(phase='saving_file'))
        folder = Path(temporary.name)
        source = folder / Path((file.filename or 'source.xlsx').replace('\\', '/')).name
        if source.suffix.lower() != '.xlsx':
            raise ValueError('Choose an .xlsx workbook')
        save_upload(file, source)
        result = standardize(source, folder, json.loads(mapping), sheet or None, header_row, allow_missing,
                             include_excel=include_excel,progress=notify)
        return FileResponse(result, media_type='application/zip', filename='converted_linelist.zip',
                            background=BackgroundTask(temporary.cleanup))
    except Exception as exc:
        notify(dict(state='failed',phase='failed',error=str(exc) if isinstance(exc,(ValueError,KeyError)) else 'Header conversion failed'))
        temporary.cleanup()
        raise HTTPException(400, str(exc) if isinstance(exc, (ValueError, KeyError)) else 'Conversion failed. Check the workbook values.') from None
    finally:
        file.file.close()
