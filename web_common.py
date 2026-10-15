from pathlib import Path
import os
ROOT = Path(__file__).parent
MAX_SIZE = int(os.environ.get('LINELIST_MAX_UPLOAD_MB', '2048')) * 1024 * 1024

def database_connection(host, port, database, username, password):
    """Use the server connection when no manual password is supplied."""
    if not password and os.environ.get('DATABASE_URL'):
        return {'conninfo': os.environ['DATABASE_URL']}
    return dict(host=host, port=port, dbname=database, user=username, password=password)
def save_upload(file, path):
    total = 0
    with path.open('wb') as output:
        while chunk := file.file.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_SIZE:
                raise ValueError(f'File exceeds the configured {MAX_SIZE // (1024 * 1024):,} MB upload limit. Increase LINELIST_MAX_UPLOAD_MB and restart the app.')
            output.write(chunk)
