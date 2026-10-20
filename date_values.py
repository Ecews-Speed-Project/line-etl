"""Date-only values and short-date Excel formatting for linelist exports."""
from datetime import date,datetime,time
from functools import lru_cache
import re

SHORT_DATE_FORMAT='dd/mm/yyyy'

@lru_cache(maxsize=256)
def is_date_heading(heading):
    from column_types import DATES
    key=''.join(c for c in heading.casefold() if c.isalnum())
    return key in {''.join(c for c in h.casefold() if c.isalnum()) for h in DATES}

def date_only(value):
    if isinstance(value,datetime):return value.date()
    if isinstance(value,date):return value
    if isinstance(value,str):
        text=value.strip()
        try:
            if re.fullmatch(r'\d{4}-\d{2}-\d{2}',text):return date.fromisoformat(text)
            if re.match(r'^\d{4}-\d{2}-\d{2}[ T]',text):return datetime.fromisoformat(text.replace('Z','+00:00')).date()
        except ValueError:pass
    return None

def json_date_value(heading,value):
    if isinstance(value,(datetime,date)) or is_date_heading(heading):
        parsed=date_only(value)
        if parsed is not None:return parsed.isoformat()
    return value.isoformat() if isinstance(value,time) else value
