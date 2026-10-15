"""Thread-safe, credential-free progress for database operations."""
import threading
import time
import uuid

LOCK=threading.RLock()
OPERATIONS={}


def create(kind):
    if kind not in ('upload','flatten'):raise ValueError('Invalid operation kind')
    with LOCK:
        for key in list(OPERATIONS):
            if time.time()-OPERATIONS[key]['created_at']>86400:OPERATIONS.pop(key)
        key=uuid.uuid4().hex
        OPERATIONS[key]=dict(id=key,kind=kind,state='waiting',phase='waiting',created_at=time.time(),processed=0,inserted=0,skipped=0)
        return dict(OPERATIONS[key])


def get(key):
    with LOCK:
        if key not in OPERATIONS:raise ValueError('Progress expired or server restarted')
        return dict(OPERATIONS[key])


def callback(key,kind):
    if not key:return lambda event:None
    with LOCK:
        operation=get(key)
        if operation['kind']!=kind or operation['state']!='waiting':raise ValueError('Invalid or already used progress ID')
        OPERATIONS[key].update(state='running')
    def update(event):
        with LOCK:
            OPERATIONS[key].update(event)
    return update
