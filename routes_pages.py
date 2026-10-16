from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from web_common import ROOT
import os
import re
router=APIRouter()

def display(name,quarterly=False):
    content = (ROOT/name).read_text(encoding='utf-8')
    if quarterly:
        content=content.replace('<body','<body data-api-prefix="/quarterly"',1)
        for path in ('upload','flat','errors','dashboard'):
            content=content.replace('href="/'+path+'"','href="/quarterly/'+path+'"')
        content=content.replace('Upload & review','Quarterly upload & review').replace('Flatten uploaded records','Flatten quarterly records').replace('<h1>Correct type errors</h1>','<h1>Quarterly type corrections</h1>')
        content=content.replace('Reporting period','Quarterly reporting date').replace('value="public"','value="quarterly" readonly')
        if name=='upload.html':
            content=content.replace('Quarterly reporting date','Quarterly reporting period')
            content=content.replace('type="date" name="period"','type="text" name="period" placeholder="FY26Q4"')
            content=content.replace('Choose the reporting date for this linelist.','Enter the fiscal quarter, for example FY26Q1 or FY26Q4.')
        content=content.replace('type="date" name="period"','type="text" name="period" placeholder="FY26Q4"')
        content=content.replace('The date is saved with every row and carried into linelist_flat.','The quarter label is saved as text with every row and carried into quarterly.linelist_flat.')
        content=content.replace('Each row includes its reporting period as a DATE.','Each row includes its fiscal quarter as TEXT, for example FY26Q4.')
        for field in ('table','source_table'):
            content=re.sub(r'(<input\b[^>]*name="'+field+r'"[^>]*)(>)',r'\1 readonly\2',content)
        content=content.replace('</nav>','</nav><p class="hint">Quarterly workflow · PostgreSQL tables quarterly.linelist_records and quarterly.linelist_flat. Weekly records and copied-row flags are separate.</p>',1)
        content=content.replace('<strong>linelist_flat</strong>','<strong>quarterly.linelist_flat</strong>')
        content=content.replace('Linelist dashboard','Quarterly linelist dashboard').replace('Treatment and viral load report','Quarterly treatment and viral load report')
        content=content.replace('>Dashboard</a>','>Quarterly dashboard</a>')
        content=content.replace('</nav>','<a href="/dashboard">Weekly dashboard</a></nav>',1)
        content=content.replace('</nav>','<a href="/upload">Weekly upload &amp; review</a><a href="/flat">Weekly flat table</a></nav>',1)
    else:
        content=content.replace('</nav>','<a href="/quarterly/upload">Quarterly upload &amp; review</a><a href="/quarterly/flat">Quarterly flat table</a><a href="/quarterly/errors">Quarterly type corrections</a><a href="/quarterly/dashboard">Quarterly dashboard</a></nav>',1)
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


@router.get('/quarterly/upload')
def quarterly_upload():return display('upload.html',quarterly=True)

@router.get('/quarterly/flat')
def quarterly_flat():return display('flat.html',quarterly=True)

@router.get('/quarterly/errors')
def quarterly_errors():return display('errors.html',quarterly=True)


@router.get('/quarterly/dashboard')
def quarterly_dashboard():return display('dashboard.html',quarterly=True)
