# Cultiva

Cultiva is a Python/Tkinter garden and farm planner backed by MySQL.

## Setup

1. Install Python 3.10 or newer.
2. Install MySQL Server (or start MySQL from XAMPP).
3. Open a terminal in the project folder and install dependencies:

   ```bash
   python -m pip install -r requirements.txt
   ```

4. Copy `env.example` to `src/.env`, then edit the MySQL values. Example:

   ```ini
   DB_HOST=127.0.0.1
   DB_PORT=3306
   DB_USER=root
   DB_PASSWORD=
   DB_NAME=farm_garden_planner
   ```

   Use your actual MySQL username and password. Do not commit a real `.env` file.

5. Initialize or safely update the database schema:

   ```bash
   cd src
   python setup_db.py
   ```

   The setup script uses `CREATE TABLE IF NOT EXISTS`; it does not reset or delete existing data unless the destructive `--reset` option is explicitly supplied.

6. Start Cultiva:

   ```bash
   python app.py
   ```

## Universal Import

Open **Library → Import files**.

- Any supported, non-executable file can be stored in the central Library.
- Identical file contents are deduplicated using SHA-256.
- CSV, XLSX and XLS spreadsheets can be previewed, mapped, validated and imported into every existing user-data module: Crops, Workers, Plots, Plantings, Tasks, Shifts, Attendance, Journal and Notes. Related records are resolved by their names (for example, a planting row must reference an existing plot and crop); import prerequisite records first.
- Required fields are marked with `*`. Automatic mapping is a suggestion; confirm or change it before importing.
- Invalid rows are excluded and reported. Existing matching records are skipped; imports never update or overwrite existing records.
- PDF, Word, image, audio, video and other safe file types are stored as Library resources and opened with the operating system's associated application.

## Resource integration

`resources` is the centralized file registry. `resource_links` allows one resource to be linked to multiple existing module records without copying the physical file. The helper API is in `src/helpers/universal_import.py`:

- `link_resource(resource_id, module_key, record_id)`
- `unlink_resource(resource_id, module_key, record_id)`
- `resources_for_record(module_key, record_id)`
- `resource_usage(resource_id)`

Supported module keys are restricted to existing Cultiva tables.

## Database migration

New installations receive the `resources` and `resource_links` tables through `src/schema.sql` when Cultiva starts. Existing databases are upgraded with non-destructive `CREATE TABLE IF NOT EXISTS` statements. A standalone script is also provided at `database/migrations/001_universal_resources.sql`.

## Notes and limitations

- The existing `attachments` feature for Notes and Journal entries is retained unchanged.
- XLSX uses `openpyxl`; legacy XLS uses `xlrd`. Install all dependencies from `requirements.txt`.
- System configuration (`settings`) and the internal Library registry (`resources`, `resource_links`) are intentionally not spreadsheet destinations. File attachments remain managed through the existing attachment workflow. The Calendar is populated by imported Tasks and Plantings; it is a view of those records, not a separate table.
- MySQL integration tests require a running MySQL server and valid credentials. The source archive does not include database credentials or a database server.
- Imported files are never executed. Executable and script extensions are blocked. File size remains limited by the existing 25 MB application upload limit.


## Farm and Garden data separation

On startup, Cultiva runs an idempotent database migration that creates the
`cultivation_modes` lookup table and adds `mode_id` ownership to the farm/garden
modules, attachments, and Library resources. All records already in the database
are assigned to Farm (`mode_id = 1`); Garden (`mode_id = 2`) starts empty.
The application scopes every mode-owned table in SELECT statements, including
all tables in multi-table and LEFT JOIN queries. Inserts, updates, and deletes
are also constrained to the selected mode. The SQL boundary is shared by the
Today, Agenda, Calendar, Timetable, Attendance, Manage, Notes, Journal, Library,
and portable import/export workflows. Composite foreign keys prevent a record
from linking to a parent in the other mode. `.cultiva` exports contain only the
active mode; imports are applied
to whichever mode is active when the import is started. The migration does not drop or recreate existing application tables. The
one-time `migration_mode_separation_farm_backfill_v2` marker ensures all records
that existed before this corrected release are assigned to Farm exactly once;
Garden starts empty. Back up the MySQL database before the first launch of this
release. The migration is idempotent after its marker is written.
