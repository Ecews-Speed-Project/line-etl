from web_common import database_connection
from fastapi import APIRouter,Form,HTTPException
from dashboard import summary
router=APIRouter()

@router.post('/api/dashboard')
def dashboard(host:str=Form('localhost'),port:int=Form(5432),database:str=Form('ecews'),
              username:str=Form('postgres'),password:str=Form(''),schema:str=Form('public'),
              source_table:str=Form('linelist_records'),period:str=Form('')):
    try:
        return summary(database_connection(host, port, database, username, password),schema,source_table,period or None)
    except ValueError as exc:
        raise HTTPException(400,str(exc)) from None
    except Exception:
        raise HTTPException(400,'Could not load the dashboard. Check your connection and source table permissions.') from None
