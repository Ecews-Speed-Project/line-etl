from pathlib import Path
import json
import tempfile
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from web_common import save_upload
router = APIRouter()
from excel_to_json import convert


@router.post('/api/convert')
def convert_excel(file: UploadFile = File(...), sheet: str = Form(''),
                  header_row: int = Form(1)):
    if not (file.filename or '').lower().endswith('.xlsx'):
        raise HTTPException(400, 'Choose an .xlsx workbook')
    temporary = tempfile.TemporaryDirectory(prefix='linelist_')
    folder = Path(temporary.name)
    try:
        source = folder / Path(file.filename.replace('\\', '/')).name
        save_upload(file, source)
        result = folder / 'linelist.json'
        report = {}
        count = convert(source, result, sheet or None, header_row, report=report)
        return FileResponse(result, media_type='application/json', filename='linelist.json',
                            headers={'X-Row-Count': str(count), 'X-Flagged-Cells': str(report['flagged_cells'])},
                            background=BackgroundTask(temporary.cleanup))
    except Exception as exc:
        temporary.cleanup()
        message = str(exc) if isinstance(exc, (ValueError, KeyError)) else 'Could not read this workbook. Check that it is a valid Excel file.'
        raise HTTPException(400, message) from None
    finally:
        file.file.close()
