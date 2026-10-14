"""FastAPI application: shared middleware, static assets and module routers."""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from web_common import ROOT, save_upload
import web_common
from routes_pages import router as pages
from routes_excel import router as excel
from routes_mapping import router as mapping
from routes_upload import router as upload
from routes_flat import router as flat
from routes_dashboard import router as dashboard

app=FastAPI(title='Linelist Workspace')
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','testserver'])
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
for router in (pages,excel,mapping,upload,flat,dashboard):
    app.include_router(router)

@app.exception_handler(Exception)
async def unexpected_error(request,exc):
    return JSONResponse(status_code=500,content={'detail':'Processing failed. Please try again or check the server log.'})

@app.middleware('http')
async def local_requests(request,call_next):
    if request.method=='POST' and request.headers.get('origin') not in (None,'http://127.0.0.1:8000','http://localhost:8000'):
        return HTMLResponse('Request origin is not allowed',status_code=403)
    return await call_next(request)
