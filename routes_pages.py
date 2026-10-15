from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from web_common import ROOT
import os
import re
router=APIRouter()

def display(name):
    content = (ROOT/name).read_text(encoding='utf-8')
    if os.environ.get('APP_ACCESS_PASSWORD'):
        content = content.replace('</nav>', '</nav><form action="/logout" method="post"><button type="submit">Sign out</button></form>')
    if os.environ.get('DATABASE_URL'):
        # Keep the configured connection and password entirely on the server.
        content = re.sub(r'<input\b[^>]*name="(?:host|port|database|username|password)"[^>]*>',
                         lambda match: re.sub(r'\srequired\b', '', match.group()).replace('<input', '<input disabled'),
                         content)
        content = content.replace('<form ', '<p class="hint">Using the database connection configured on the server.</p><form ')
    return HTMLResponse(content)

@router.get('/')
def home(): return display('index.html')

@router.get('/dashboard')
def dashboard(): return display('dashboard.html')

@router.get('/headers')
def headers(): return display('headers.html')

@router.get('/convert')
def convert(): return display('convert.html')

@router.get('/upload')
def upload(): return display('upload.html')

@router.get('/flat')
def flat(): return display('flat.html')

@router.get('/errors')
def errors(): return display('errors.html')
