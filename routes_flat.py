from web_common import database_connection
from pathlib import Path
import json
import tempfile
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from web_common import save_upload
router = APIRouter()
from flatten_json import flatten, browse, type_errors
from correct_types import correct
from operation_progress import callback


@router.post('/api/correct-type')
def correct_type(host: str = Form('localhost'), port: int = Form(5432), database: str = Form('ecews'),
                 username: str = Form('postgres'), password: str = Form(''), schema: str = Form('public'),
                 source_table: str = Form(...), source_sha256: str = Form(...), sheet: str = Form(...),
                 source_row: int = Form(...), heading: str = Form(...), value: str = Form(...)):
    try:
        return correct(database_connection(host, port, database, username, password),
                       schema,source_table,source_sha256,sheet,source_row,heading,value)
    except ValueError as exc:
        raise HTTPException(400,str(exc)) from None
    except Exception:
        raise HTTPException(400,'Correction could not be saved. No partial changes were applied.') from None


@router.post('/api/flat/{action}')
def flat_action(action: str, host: str = Form('localhost'), port: int = Form(5432),
                database: str = Form('ecews'), username: str = Form('postgres'),
                password: str = Form(''), schema: str = Form('public'),
                source_table: str = Form('linelist_records'), offset: int = Form(0), limit: int = Form(25),
                period: str = Form(''),progress_id:str=Form('')):
    connection = database_connection(host, port, database, username, password)
    notify=lambda event:None
    try:
        if action == 'build':
            notify=callback(progress_id,'flatten')
            return flatten(connection, schema, source_table,progress=notify)
        if action == 'browse':
            return browse(connection, schema, offset, limit, period=period or None)
        if action == 'errors':
            return type_errors(connection, schema, offset, limit)
        raise ValueError('Unknown action')
    except ValueError as exc:
        notify(dict(state='failed',phase='failed',error=str(exc),committed=0))
        raise HTTPException(400, str(exc)) from None
    except Exception:
        notify(dict(state='failed',phase='failed',error='Flattening failed; transaction rolled back.',committed=0))
        raise HTTPException(400, 'Database operation failed. Check your connection, permissions and source table. Create linelist_flat before browsing it.') from None
