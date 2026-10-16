"""FastAPI application: shared middleware, static assets and module routers."""
import os
from urllib.parse import urlsplit
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from auth import router as auth_router, authenticated
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
from routes_jobs import router as jobs
from routes_progress import router as progress
from routes_treatment import router as treatment
from routes_quarterly import router as quarterly

app=FastAPI(title='Linelist Workspace')
app.include_router(auth_router)
allowed_hosts = ['127.0.0.1', 'localhost', 'testserver'] + [
    host.strip() for host in os.environ.get('ALLOWED_HOSTS', '').split(',') if host.strip()]
public_hostname = urlsplit(os.environ.get('PUBLIC_ORIGIN', '')).hostname
if public_hostname:
    allowed_hosts.append(public_hostname)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
app.mount('/static',StaticFiles(directory=ROOT/'static'),name='static')
for router in (pages,excel,mapping,upload,flat,dashboard,jobs,progress,treatment,quarterly):
    app.include_router(router)

@app.get('/healthz')
def health():
    return {'status': 'ok'}

@app.exception_handler(Exception)
async def unexpected_error(request,exc):
    return JSONResponse(status_code=500,content={'detail':'Processing failed. Please try again or check the server log.'})

@app.middleware('http')
async def local_requests(request,call_next):
    access_password = os.environ.get('APP_ACCESS_PASSWORD')
    public_paths = {'/healthz', '/login', '/static/import.css'}
    if access_password and request.url.path not in public_paths and not authenticated(request):
        if request.url.path.startswith(('/api/','/quarterly/api/')):
            return JSONResponse({'detail': 'Your session has expired. Please sign in again.'}, status_code=401)
        return RedirectResponse('/login', status_code=303)
    allowed_origins = {None, 'http://127.0.0.1:8000', 'http://localhost:8000',
                       'http://127.0.0.1:5003', 'http://localhost:5003'}
    public_origin = os.environ.get('PUBLIC_ORIGIN', '').rstrip('/')
    if public_origin:
        allowed_origins.add(public_origin)
    allowed_origins.update(origin.strip().rstrip('/') for origin in
                           os.environ.get('ADDITIONAL_ORIGINS', '').split(',') if origin.strip())
    if request.method=='POST' and request.headers.get('origin') not in allowed_origins:
        return HTMLResponse('Request origin is not allowed',status_code=403)
    response = await call_next(request)
    if access_password:
        response.headers['Cache-Control'] = 'no-store'
    return response
