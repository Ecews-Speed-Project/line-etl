from fastapi import APIRouter,HTTPException
from operation_progress import create,get
router=APIRouter()

@router.post('/api/progress/{kind}')
def create_progress(kind:str):
    try:return create(kind)
    except ValueError as exc:raise HTTPException(400,str(exc)) from None

@router.get('/api/progress/{operation_id}')
def progress(operation_id:str):
    try:return get(operation_id)
    except ValueError as exc:raise HTTPException(404,str(exc)) from None
