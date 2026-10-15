"""Start the local app with a persistent, private administrator login."""
import os
from pathlib import Path
import secrets

ROOT = Path(__file__).parent


def configure():
    path = ROOT / '.env'
    lines = path.read_text(encoding='utf-8').splitlines() if path.exists() else []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or '=' not in stripped:
            continue
        key, value = stripped.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('\"\''))
    defaults = {'APP_ACCESS_USERNAME': 'admin', 'APP_ACCESS_PASSWORD': secrets.token_urlsafe(18),
                'APP_SESSION_SECRET': secrets.token_hex(32)}
    changed = False
    for key, fallback in defaults.items():
        if not os.environ.get(key):
            os.environ[key] = fallback
            lines = [line for line in lines if not line.strip().startswith(key+'=')]
            lines.append(key+'='+fallback)
            changed = True
    if changed or not path.exists():
        path.write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return os.environ['APP_ACCESS_USERNAME']


if __name__ == '__main__':
    username = configure()
    print('Open http://127.0.0.1:8000/login')
    print('Username: '+username+'. Password is saved in the local .env file.')
    import uvicorn
    uvicorn.run('app:app', host='127.0.0.1', port=8000)
