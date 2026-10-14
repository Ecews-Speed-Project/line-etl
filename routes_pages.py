from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from web_common import ROOT
router=APIRouter()

def display(name):
    return HTMLResponse((ROOT/name).read_text(encoding='utf-8'))

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
