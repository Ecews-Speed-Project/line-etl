from pathlib import Path
import os
ROOT = Path(__file__).parent
MAX_SIZE = int(os.environ.get('LINELIST_MAX_UPLOAD_MB', '2048')) * 1024 * 1024
def save_upload(file, path):
    total = 0
    with path.open('wb') as output:
        while chunk := file.file.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_SIZE:
                raise ValueError(f'File exceeds the configured {MAX_SIZE // (1024 * 1024):,} MB upload limit. Increase LINELIST_MAX_UPLOAD_MB and restart the app.')
            output.write(chunk)
