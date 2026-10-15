"""Password login with expiring, signed browser sessions."""
import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from web_common import ROOT

router = APIRouter()
COOKIE = 'linelist_session'
MAX_AGE = 8 * 60 * 60
_fallback_key = secrets.token_hex(32)
_attempts = defaultdict(deque)


def signature(payload):
    key = (os.environ.get('APP_SESSION_SECRET', _fallback_key) + ':' +
           os.environ.get('APP_ACCESS_USERNAME', 'admin') + ':' +
           os.environ.get('APP_ACCESS_PASSWORD', '')).encode()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def authenticated(request):
    token = request.cookies.get(COOKIE, '')
    try:
        expires, nonce, digest = token.split('.')
        payload = expires + '.' + nonce
        return (time.time() < int(expires) <= time.time() + MAX_AGE + 5 and
                hmac.compare_digest(digest, signature(payload)))
    except (ValueError, TypeError):
        return False


def login_page(error='', status=200):
    content = (ROOT / 'login.html').read_text(encoding='utf-8')
    return HTMLResponse(content.replace('{{error}}', error), status_code=status,
                        headers={'Cache-Control': 'no-store'})


@router.get('/login')
def show_login(request: Request):
    if authenticated(request):
        return RedirectResponse('/', status_code=303)
    return login_page()


@router.post('/login')
def login(request: Request, username: str = Form(''), password: str = Form('')):
    client = request.client.host if request.client else 'unknown'
    attempts = _attempts[client]
    now = time.time()
    while attempts and attempts[0] < now - 60:
        attempts.popleft()
    if len(attempts) >= 5:
        return login_page('Too many attempts. Please try again in one minute.', 429)
    expected_password = os.environ.get('APP_ACCESS_PASSWORD', '')
    username_ok = secrets.compare_digest(username.encode(), os.environ.get('APP_ACCESS_USERNAME', 'admin').encode())
    password_ok = secrets.compare_digest(password.encode(), expected_password.encode())
    if not expected_password or not (username_ok and password_ok):
        attempts.append(now)
        return login_page('Incorrect username or password.', 401)
    attempts.clear()
    payload = str(int(now) + MAX_AGE) + '.' + secrets.token_hex(16)
    response = RedirectResponse('/', status_code=303)
    response.set_cookie(COOKIE, payload + '.' + signature(payload), max_age=MAX_AGE,
                        httponly=True, samesite='strict',
                        secure=request.url.scheme == 'https' or
                        request.headers.get('x-forwarded-proto') == 'https')
    response.headers['Cache-Control'] = 'no-store'
    return response


@router.post('/logout')
def logout():
    response = RedirectResponse('/login', status_code=303)
    response.delete_cookie(COOKIE)
    return response
