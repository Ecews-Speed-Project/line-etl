# Linelist ETL

A local FastAPI app for standardizing Excel linelists, converting them to JSON,
loading PostgreSQL, typed flattening, corrections and reporting.

## Run

Requires Python 3.11+ and PostgreSQL. On Windows, double-click `start_app.bat`,
then open http://127.0.0.1:8000. Keep the terminal running while using the app.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Enter database credentials on the relevant page. Defaults are localhost:5432,
database `ecews`, user `postgres`. No password is bundled or saved. The database
must exist; the account needs table/index/function creation permissions and
SELECT, INSERT and UPDATE access. Add authentication and HTTPS before exposing
this localhost application to other computers.

## Pages

| Page | Purpose |
| --- | --- |
| `/` | Module navigation |
| `/headers` | Map old Excel headings to the current 121-column schema |
| `/convert` | Convert Excel to JSON and review flagged cells |
| `/upload` | Review JSON, choose a reporting date and upload |
| `/flat` | Flatten records, browse typed columns and filter by period |
| `/errors` | Correct invalid values in source and flat records |
| `/dashboard` | Uploaded rows, active counts and flattening status by period |

Each API module has a separate `routes_*.py` file. `app.py` configures middleware,
static assets and routing. Include the HTML pages and `static/` when copying the app.

## Data handling

`current_headers.json` contains column names only. Exact and unique formatting
matches are automatic; IPT/TPT renames require review. Missing target and unmapped
source headings are flagged. Mapped downloads contain standardized Excel,
upload-ready JSON, mapping and cell-error reports, and original data.

Formula cells use results saved by Excel; no formulas are recalculated. Saved
results may be stale. Excel errors and formulas without saved results become null
and appear in the review. Flagged JSON requires acknowledgment before upload.
Blank or duplicate headings are rejected.

The default upload limit is 2 GB per file; configure `LINELIST_MAX_UPLOAD_MB` to
change it. Large JSON operations require sufficient RAM and temporary disk space.
Uploaded temporary files are removed after processing.

## Database

- `linelist_records`: JSONB rows, source metadata and reporting `period` DATE.
- `linelist_flat`: 121 current columns plus `period`, using DATE, INTEGER,
  NUMERIC and TEXT types defined in `column_types.py`.
- `linelist_flat_imports`: copied-row tracking for repeat flattening.
- `linelist_flat_type_errors`: original invalid values and correction audit.
- `linelist_flat_text_backup`: initial text-table backup when migrating older
  installations; not refreshed on subsequent imports.

All linelist date fields use DATE without time. Identifiers and categories remain
text. Invalid typed values become null and are flagged rather than guessed.
Dates must be ISO; ambiguous locale dates and numeric date serials are flagged.

A reporting period is required for new uploads. Identical snapshot and period
uploads are skipped. A different period creates a separate snapshot. Original
snapshot hashes are retained. Existing rows without a period are not assigned
a guessed date. Flattening skips tracked source rows. This is snapshot storage,
not patient deduplication across periods or files.

Corrections validate the type and update source JSONB, the matching flat row and
the audit record atomically. Ambiguous matches are rejected without changes.
Original error values and copied-row tracking are retained; resolved errors leave
the pending review.

Dashboard active counts use `CurrentARTStatus = Active`, ignoring case and
surrounding spaces. Counts represent source rows within each snapshot.

## Command line

```powershell
.\.venv\Scripts\python.exe excel_to_json.py "C:\path\linelist.xlsx" linelist.json
.\.venv\Scripts\python.exe upload_json.py linelist.json --dry-run
$env:PGHOST = 'localhost'
$env:PGPORT = '5432'
$env:PGDATABASE = 'ecews'
$env:PGUSER = 'postgres'
.\.venv\Scripts\python.exe upload_json.py linelist.json --period 2026-10-14
```

The uploader prompts securely if `PGPASSWORD` is unset. `.env` files are not
loaded. Configure `PGSSLMODE` and `PGSSLROOTCERT` as required by your database.
Batch scripts are included for both steps.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pip install httpx
.\.venv\Scripts\python.exe -m unittest discover
```

Tests use generated workbook fixtures and mocked database API calls. Patient
files, generated JSON, spreadsheets, logs and credentials are excluded from Git.
