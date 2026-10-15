"""Stream gzip files with an explicit expanded-size limit."""
import gzip
import io
import json
import os
import zlib
from pathlib import Path


class LimitedReader(io.RawIOBase):
    def __init__(self,stream,limit,notify,compressed,raw,total):
        self.stream,self.limit,self.notify=stream,limit,notify
        self.compressed,self.raw,self.total=compressed,raw,total
        self.count,self.reported=0,0

    def readable(self):return True

    def readinto(self,buffer):
        data=self.stream.read(min(len(buffer),65536))
        self.count+=len(data)
        if self.count>self.limit:
            raise ValueError('Expanded JSON exceeds LINELIST_MAX_JSON_MB; increase the setting only if the server has sufficient memory')
        buffer[:len(data)]=data
        if self.count-self.reported>=4*1024*1024 or not data:
            self.reported=self.count
            self.notify(dict(phase='decompressing_json' if self.compressed else 'reading_json',
                             decompressed_bytes=self.count,compressed_bytes=self.raw.tell(),compressed_total=self.total))
        return len(data)


def load_json(path,notify,reject_constant):
    path=Path(path)
    limit=int(os.environ.get('LINELIST_MAX_JSON_MB','2048'))*1024*1024
    with path.open('rb') as raw:
        magic=raw.read(2);raw.seek(0)
        compressed=magic==b'\x1f\x8b' or path.name.lower().endswith('.gz')
        notify(dict(phase='decompressing_json' if compressed else 'reading_json'))
        stream=gzip.GzipFile(fileobj=raw,mode='rb') if compressed else raw
        try:
            with io.TextIOWrapper(io.BufferedReader(LimitedReader(stream,limit,notify,compressed,raw,path.stat().st_size)),encoding='utf-8-sig') as text:
                document=json.load(text,parse_constant=reject_constant)
        except (gzip.BadGzipFile,EOFError,OSError,UnicodeDecodeError,zlib.error):
            raise ValueError('Cannot read JSON: the gzip file may be corrupt, truncated or not UTF-8 JSON') from None
        finally:
            if compressed:stream.close()
    return document


def compress_json(source,destination,progress=None):
    source,destination=Path(source),Path(destination)
    partial=destination.with_suffix(destination.suffix+'.part')
    size=source.stat().st_size
    done=0
    try:
        with source.open('rb') as original,gzip.open(partial,'wb',compresslevel=3) as output:
            while chunk:=original.read(1024*1024):
                output.write(chunk);done+=len(chunk)
                if progress:progress(dict(phase='compressing',bytes_done=done,bytes_total=size))
        os.replace(partial,destination)
    finally:
        partial.unlink(missing_ok=True)
