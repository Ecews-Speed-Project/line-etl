"""Quarterly routes reuse the weekly pipeline inside a fixed, isolated schema."""
from fastapi import APIRouter,Depends,HTTPException,Request
from routes_upload import router as upload_router
from routes_flat import router as flat_router
from routes_dashboard import router as dashboard_router
from routes_treatment import router as treatment_router

async def quarterly_scope(request:Request):
    form=await request.form()
    if form.get('schema')!='quarterly':
        raise HTTPException(400,'Quarterly operations must use the quarterly schema.')
    for field in ('table','source_table'):
        if field in form and form[field]!='linelist_records':
            raise HTTPException(400,'Quarterly operations use the linelist_records source table.')

router=APIRouter(prefix='/quarterly',dependencies=[Depends(quarterly_scope)])
router.include_router(upload_router)
router.include_router(flat_router)

router.include_router(dashboard_router)
router.include_router(treatment_router)
