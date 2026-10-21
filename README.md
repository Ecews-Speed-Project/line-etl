# Linelist ETL

## Treatment and viral load reporting

Load the dashboard, select one uploaded linelist and choose a reporting end date
(default 2026-09-19). Calculate report displays TxCurr, Eligible, Sample collected,
Result, VL suppression, Undetectable, LLV, Unsuppressed and four rates, with
paediatric, adult and unknown-age breakdowns. Download Word report produces a
two-page brief based on the retained Word template using the same selection.

TxCurr uses Active in CurrentARTStatus. The VL eligibility counts require Active and
DaysOfARVRefill >=180. Sample and result dates must fall within the inclusive
calendar-year window ending on the selected date. A valid Result also requires a
finite numeric CurrentViralLoad >=0. Suppression is <1000, undetectable <50, LLV
is >=50 and <1000, and unsuppressed is Result minus suppression. Coverage divides
Result by Eligible; suppression, undetectable and LLV rates divide by Result.
Zero denominators are N/A. Status is taken from the selected snapshot rather than
reconstructed at the report date. Counts assume one client per source row.
The dashboard also computes treatment activity indicators and IIT using their separate windows. NetNew and the selected CoT snapshot ratio use the quarterly comparison. IIT rate is IIT / (previous-quarter TxCurr + TxNew) x 100, displayed to one decimal place.

## Faster current-heading conversion

Header standardization now writes mapped JSON and the original-data copy while
reading worksheet rows, without loading the complete intermediate JSON back into
memory. The header-mapping page defaults to JSON-only output; select “Also generate
an Excel workbook” if you need an Excel copy. JSON, JSON.gz and mapping/error
reports remain included. API clients retain include_excel=true as the default.
Progress covers upload, workbook reading, mapped rows, optional Excel creation,
compression and packaging. Already-compressed Excel/gzip files are stored directly
in the ZIP, while JSON uses fast compression.

## Compressed JSON transfers

Use Download JSON.gz after Excel conversion to transfer a smaller file. The
header-mapping ZIP also contains linelist.json.gz. Review and PostgreSQL upload
accept .json and .json.gz. Compressed files are first saved to the local temporary
upload path, then decompressed through a bounded gzip reader directly into the
JSON parser; a separate extracted JSON file is not written. Progress includes
the decompression stage and expanded MB, followed by validation and database rows.

LINELIST_MAX_JSON_MB limits expanded JSON size (default 2048 MB), independently
of the uploaded-file limit. Corrupt or truncated gzip uploads are rejected before
database writes. The JSON parser still holds the parsed document in memory;
compression reduces transfer size, not the memory needed for parsed records.
Plain and compressed copies preserve the same snapshot hash and reporting period
and therefore use the same duplicate-skipping behavior. Gzip downloads are served
as attachments, without Content-Encoding, so the browser keeps the .gz file.

## Database progress

JSON uploads display file-transfer progress followed by JSON reading, validation,
row insertion and commit status. Records insert in batches of 500 within a single
transaction. The already-validated JSON document is reused rather than parsed
multiple times. Flattening snapshots source-row keys in temporary PostgreSQL
tables, identifies already copied rows and processes pending rows in batches of
2,000. Progress shows rows processed, inserted and skipped. Intermediate counts
are uncommitted; success appears only after the whole transaction commits.
On failure, new rows and copied-row tracking roll back together.
Database progress is polled from the server; keep the upload/flattening page
open until completion. These operation counters are in memory and reset when the
server restarts. Credentials and patient values are not stored in progress state.

## Conversion progress and local files

The Excel-to-JSON page first streams the raw workbook to a local job directory
without multipart buffering, then starts a background conversion. The UI shows
upload percentage, queued status, hashing, workbook opening, worksheet rows
examined, JSON records written and finalization. Row totals use the worksheet's
declared dimension; worksheets with no dimension show counts without a percentage.
The conversion worker handles one workbook at a time to limit concurrent memory.
Rows are read using openpyxl read-only mode and JSON records are written to disk
incrementally. Excel metadata and shared strings still require memory.

JSON downloads are streamed from the server file. The error preview loads a
separate report instead of loading and re-uploading the complete JSON. Progress
can be resumed by returning to the conversion page in the same browser tab.
Jobs live in the ignored `.local_jobs/` folder, or LINELIST_JOB_DIR if configured.
Use Remove local files after downloading to remove a completed or failed job.
Server restarts preserve completed downloads; interrupted jobs must be uploaded
again. The existing synchronous /api/convert endpoint is retained for API clients.

## Local sign-in

`start_app.bat` runs `run_local.py`, which loads the local `.env` file and enables
administrator login. On the first local start, it creates a random password and
session secret if none are configured. Open http://127.0.0.1:8000/login and use
the APP_ACCESS_USERNAME and APP_ACCESS_PASSWORD values in `.env`. Edit those
values and restart to change them. This file is excluded from Git.

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

## Docker

```powershell
Copy-Item .env.example .env
# Set DATABASE_URL in .env, then:
docker compose up --build -d
```

Open http://127.0.0.1:5003. For PostgreSQL running on the Windows host, enter
`host.docker.internal` as the database host on the relevant page. PostgreSQL
must accept connections from Docker. The existing database is not bundled.
Run `docker compose down` to stop the app.

Docker Compose reads the ignored `.env` file. Set `DATABASE_URL` to use a
server-side connection for all database pages without entering credentials in
the browser. Leave it empty to enter connection details manually. Credentials
stay on the server when this setting is used. JWT_SECRET and RAG_SERVICE_URL
are not used by this application.

Set `APP_ACCESS_USERNAME`, `APP_ACCESS_PASSWORD` and a random
`APP_SESSION_SECRET` in `.env` to enable the login page. Signed browser sessions
expire after eight hours; use Sign out to clear the browser session. Five failed
login attempts per client in one minute temporarily block further attempts.
Configure `ALLOWED_HOSTS` and `PUBLIC_ORIGIN` for the server address and use HTTPS
for internet access. Docker publishes port 5003 on all server interfaces.

## Pages

| Page | Purpose |
| --- | --- |
| `/` | Module navigation |
| `/headers` | Map old Excel headings to the current 128-column schema |
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
- `linelist_flat`: 128 current columns plus `period`, using DATE, INTEGER,
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

Treatment report exports include a landscape state cascade, an ECEWS total calculated from all records (rates use combined denominators), and a treatment summary. Fiscal years run October to September. Undefined treatment measures display N/A until their rules and comparison data are configured.

The paediatric cascade groups Current_Age into under 1, 1-4, 5-9, 10-14 and 15-19 years by state, with state subtotals and an ECEWS total. Sample collection rate is Sample Collected / Eligible. All subtotal percentages use combined counts; missing/invalid ages are excluded. The Word download includes the paediatric cascade and treatment summary on a landscape page.

The brief now uses the retained user-supplied templates/brief_treatment.docx as its layout authority. Exports patch numerical/date text slots and replace the four table images while preserving styles, numbering, page geometry, header and unrelated package parts. The dashboard renders the same narrative spans and table models. Pillow is required for table image generation; install all requirements on the server. Undefined treatment measures remain N/A.


### Quarterly linelist workflow

Open `/quarterly/upload` to review and upload converted JSON or `.json.gz`, then `/quarterly/flat` to apply types and browse quarterly data. `/quarterly/errors` saves corrections to quarterly source and flat rows. The shared header mapping and Excel conversion modules work for either workflow.

Quarterly routes use the fixed PostgreSQL schema `quarterly`, with `linelist_records`, `linelist_flat`, copied-row tracking, type-error audit, backup and safe-cast function kept separately from the weekly `public` schema. The schema is created transactionally on the first successful quarterly upload; the database user needs permission to create it (or an administrator can pre-create it). Upload the same file/date once in each workflow without their duplicate or copied-row flags interfering. A fiscal quarter label such as `FY26Q1` or `FY26Q4` is required and saved as TEXT in both quarterly tables. Labels are trimmed and normalized to uppercase. Weekly periods remain DATE.

The APIs mirror the weekly endpoints under `/quarterly/api/`: `review-json`, `upload`, `flat/build`, `flat/browse`, `flat/errors` and `correct-type`. They require `schema=quarterly` and the standard `linelist_records` source table. Authentication and progress displays are shared. Weekly pages and existing records remain unchanged. The current dashboard continues to show the weekly data by default.

Open `/quarterly/dashboard` for quarterly upload totals by period, Active counts, flattening status, the treatment/VL report and Word export. All requests use `/quarterly/api/dashboard` and `/quarterly/api/treatment-report`, with the quarterly schema enforced. Selecting a snapshot resolves its fiscal quarter label to a reporting end date: FY26Q1 ends 2025-12-31, Q2 ends 2026-03-31, Q3 ends 2026-06-30 and Q4 ends 2026-09-30. The label itself stays unchanged in storage and reports. No quarterly uploads produces an empty dashboard, and quarterly Word files use a `quarterly_` prefix. The weekly dashboard remains at `/dashboard`.

For older installations, quarterly writes migrate existing DATE period columns to TEXT transactionally, preserving their existing ISO date values, row identities and copied-row tracking. No existing weekly column is migrated.

On the weekly dashboard, select a weekly snapshot and an optional Quarterly comparison linelist. The comparison selector lists quarterly uploaded snapshots by fiscal label, filename and sheet. The selected quarterly snapshot supplies state and paediatric TxCurr counts for the quarter comparison column in both preview and Word export; weekly TxCurr stays in the current column. Without a selected quarterly snapshot the comparison stays N/A. Missing states in the selected comparison are N/A. The report date continues to control the viral-load reporting window.

With both weekly and quarterly snapshots selected, NetNew is weekly Active TxCurr minus quarter Active TxCurr. CoT/retention is weekly TxCurr divided by quarter TxCurr times 100, as selected by the user. State, paediatric-state, paediatric total and ECEWS values are calculated independently from their counts; total rates are not averages of state rates. This is a snapshot ratio, not matched-client cohort retention; rates may exceed 100%. Missing comparisons and zero denominator rates show N/A. Tables, narrative, Word export and API comparison_metrics use the same calculations.


### Treatment activity indicators

The report has a separate inclusive activity window, defaulting to 2026-07-01 through 2026-09-30. TxNew counts ARTStartDate in that window, explicitly excluding TI=YES; blank TI is included as requested. Transferred in counts Date_Transfered_In in the window. Death, Stopped and Transferred out require Outcomes_Date in the window and CurrentARTStatus equal to Death, Discontinued care and Transferred out respectively. These indicators do not apply the VL Active/refill eligibility filters.

RTT compares the selected quarterly snapshot with current Active records: previous status must be neither Active nor blank. It has no event-date condition. Matching uses facility (Datim_Code, otherwise FacilityName) and PepID, with patient_id as fallback; identifiers are trimmed/case-insensitive. Duplicate or conflicting identities are excluded, and unmatched/ambiguous Active rows appear in report quality counts. A missing comparison gives N/A. Matching indexes are stored in a temporary local SQLite file and removed after calculation; PostgreSQL reads are streamed. Current age and state determine breakdowns.

All six indicators appear in the dashboard activity summary and the state/paediatric treatment tables in the preview and Word export. Invalid date counts are shown in the report notes. IIT is computed from pickup + refill + 28 days using its separate date window. IIT rate uses IIT / (selected-quarter TxCurr + TxNew) x 100. NetNew and the user-selected CoT formula are unchanged.

IIT counts CurrentARTStatus equal to LTFU or lost to follow up (case-insensitive, whitespace normalized) when Pharmacy_LastPickupdate + DaysOfARVRefill + 28 days is within the inclusive IIT window. The default is 2026-10-01 through 2026-10-17. Refill days must be finite, nonnegative whole numbers; missing/invalid inputs or overflowing dates are excluded and counted in quality notes. The IIT window is independent of the activity and VL windows. IIT is included in state/paediatric tables, narrative and dashboard totals; IIT rate uses IIT / (selected-quarter TxCurr + TxNew) x 100, with one decimal place.

IIT rate uses the selected quarterly baseline and current TxNew activity count for each state/cohort. Aggregate rates use summed IIT, quarter TxCurr and TxNew counts rather than averaging state rates. Missing comparisons or nonpositive denominators show N/A.

Future Excel downloads store date fields as genuine Excel dates with short-date formatting `dd/mm/yyyy` and no time component, including generation, sample and recapture dates. Date values in converted JSON use `YYYY-MM-DD`. Invalid date text remains visible for the existing review/correction workflow; no date is invented for it. Previously downloaded workbooks are unchanged.

Dashboard report filters: the viral load reporting start and end dates set the inclusive sample/result window. The treatment activity from/through dates apply to IIT (pickup + refill + 28), TxNew, Death, Transferred in/out and Stopped. RTT continues comparing the selected quarterly and current snapshots without a date-window restriction. Both the on-screen report and Word export use these filters.
