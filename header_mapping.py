"""Conservative header matching against the current linelist schema."""
import hashlib
import json
from pathlib import Path
import re
import zipfile

from openpyxl import Workbook, load_workbook
from excel_to_json import convert, normalize_state

TARGET = json.loads((Path(__file__).parent / 'current_headers.json').read_text(encoding='utf-8'))
SUGGESTIONS = {
    'TB_Screening_Date': 'IPT_Screening_Date',
    'Is_Patient_Eligible_For_TPT': 'Is_Patient_Eligible_For_IPT',
    'TPTOutcome': 'IPTOutcome',
    'ReasonforstoppingTPT': 'ReasonforstoppingIPT',
    'TPTOutcomeDate': 'IPTOutcomeDate',
}


def normalized(value):
    return re.sub(r'[^a-z0-9]', '', value.casefold())


def inspect_headers(source, sheet=None, header_row=1):
    if header_row < 1:
        raise ValueError('Header row must be positive')
    workbook_file = Path(source).open('rb')
    try:
        workbook = load_workbook(workbook_file, read_only=True)
    except Exception:
        workbook_file.close()
        raise
    try:
        ws = workbook[sheet] if sheet else workbook.worksheets[0]
        row = next(ws.iter_rows(min_row=header_row, max_row=header_row, values_only=True), ())
        headers = [str(v).strip() if v is not None else '' for v in row]
        while headers and not headers[-1]:
            headers.pop()
        if not headers or any(not h for h in headers) or len(set(headers)) != len(headers):
            raise ValueError('Source headings must be nonempty and unique')
        return headers
    finally:
        workbook.close()
        workbook_file.close()


def propose(headers):
    mappings, statuses = {}, {}
    for target in TARGET:
        candidates = [h for h in headers if normalized(h) == normalized(target)]
        if target in headers:
            mappings[target], statuses[target] = target, 'exact'
        elif len(candidates) == 1:
            mappings[target], statuses[target] = candidates[0], 'formatting match'
        else:
            mappings[target], statuses[target] = None, 'missing' if not candidates else 'ambiguous'
    used = {h for h in mappings.values() if h}
    return dict(target_headers=TARGET, source_headers=headers, mapping=mappings, statuses=statuses,
                unmapped_source=[h for h in headers if h not in used],
                suggestions={t: s for t, s in SUGGESTIONS.items() if not mappings[t] and s in headers})


def standardize(source, folder, mapping, sheet=None, header_row=1, allow_missing=False):
    headers = inspect_headers(source, sheet, header_row)
    if not isinstance(mapping, dict) or set(mapping) != set(TARGET):
        raise ValueError('Mapping must contain every current heading')
    selected = [s for s in mapping.values() if s is not None]
    if any(s not in headers for s in selected) or len(selected) != len(set(selected)):
        raise ValueError('Each source heading can map to only one target heading')
    missing = [t for t in TARGET if mapping[t] is None]
    if missing and not allow_missing:
        raise ValueError('Resolve missing headings or explicitly allow empty columns')
    original = folder / 'original_data.json'
    count = convert(source, original, sheet, header_row)
    doc = json.loads(original.read_text(encoding='utf-8'))
    report = dict(mapping=mapping, missing_target=missing,
                  unmapped_source=[h for h in headers if h not in selected],
                  rows=count, note='Unmapped values are preserved in original_data.json. Empty target columns contain null.')
    report['conversion_report'] = doc['conversion_report']
    original_hash = doc['source_sha256']
    doc['original_source_sha256'] = original_hash
    doc['source_sha256'] = hashlib.sha256(json.dumps([original_hash, mapping, TARGET], sort_keys=True).encode()).hexdigest()
    doc['headers'] = TARGET
    doc['mapping_report'] = report
    book = Workbook(write_only=True)
    ws = book.create_sheet('Current Linelist')
    ws.append(TARGET)
    for record in doc['records']:
        old = record['data']
        record['data'] = {t: normalize_state(t, old[mapping[t]]) if mapping[t] else None for t in TARGET}
        # Force strings to text to avoid interpreting values beginning '=' as formulas.
        from openpyxl.cell import WriteOnlyCell
        cells = []
        for value in record['data'].values():
            cell = WriteOnlyCell(ws, value=value)
            if isinstance(value, str):
                cell.data_type = 's'
            cells.append(cell)
        ws.append(cells)
    book.save(folder / 'current_linelist.xlsx')
    (folder / 'linelist.json').write_text(json.dumps(doc, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    (folder / 'mapping_report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (folder / 'cell_errors.json').write_text(json.dumps(doc['conversion_report'], indent=2), encoding='utf-8')
    result = folder / 'converted_linelist.zip'
    with zipfile.ZipFile(result, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in ('current_linelist.xlsx', 'linelist.json', 'mapping_report.json', 'cell_errors.json', 'original_data.json'):
            archive.write(folder / name, name)
    return result
