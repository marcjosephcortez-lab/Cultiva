<img width="1408" height="768" alt="Gemini_Generated_Image_f9ko87f9ko87f9ko" src="https://github.com/user-attachments/assets/fa8fb99c-a0b6-4f60-b129-8ac64e891834" />
# Cultiva

**A Python-based Farm and Garden Management System**

Cultiva is a desktop application built with **Python, Tkinter, and MySQL**. It provides a centralized platform for managing agricultural activities, organizing farm and garden records, monitoring operations, and maintaining important information in one place.

## Features

### Farm and Garden Management
- Separate Farm and Garden working modes.
- Manage agricultural records within the active mode.
- Organize crops, workers, plots, and plantings.
- Manage daily agricultural activities and operations.

### Universal Data Import
- Import records using CSV files.
- Import supported Excel spreadsheets (`.xlsx` and `.xls`).
- Preview, map, and validate data before importing.
- Automatically identify supported record types.
- Import records into their corresponding modules.
- Resolve related records using their names.
- Detect duplicate records and report invalid entries.

### Centralized Library
- Store and manage imported files and resources.
- Preview supported spreadsheet files.
- Keep a centralized registry of file resources.
- Link one stored resource to multiple application records.
- Avoid unnecessary duplication of physical files.

### Operational Management
- Crop management
- Worker management
- Plot management
- Planting records
- Task management
- Work shifts
- Attendance monitoring
- Notes and journal entries
- Calendar and daily activity views

### Portable Data Import and Export
- Export records using the `.cultiva` portable package format.
- Import previously exported Cultiva packages.
- Preserve relationships between related records.
- Prevent duplicate imports and protect existing records.

## Technologies Used

| Technology | Purpose |
|---|---|
| Python | Application programming language |
| Tkinter | Desktop graphical user interface |
| MySQL | Database management |
| OpenPyXL | Excel spreadsheet processing |
| xlrd | Legacy XLS spreadsheet processing |

## System Requirements

- Windows operating system
- Python 3.10 or newer
- MySQL Server or XAMPP with MySQL
- Required Python packages listed in `requirements.txt`

## Installation

### 1. Install Python

Download and install Python 3.10 or newer.

Download: https://www.python.org/downloads/

### 2. Install MySQL

Install MySQL Server or use XAMPP and start its MySQL service.

### 3. Download the Project

Clone the repository:

```bash
git clone https://github.com/marcjosephcortez-lab/Cultiva.git
```

Navigate to the project directory:

```bash
cd Cultiva
```

### 4. Install Dependencies

Install the required Python packages:

```bash
python -m pip install -r requirements.txt
```

### 5. Configure the Database

Copy the example environment file:

```bash
copy .env.example .env
```

Open `.env` and configure your MySQL connection settings:

```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=farm_garden_planner
```

Replace the example values with your actual MySQL configuration.

**Security reminder:** Never commit your actual `.env` file, database passwords, or private database records to GitHub.

### 6. Initialize the Database

Run the database setup script:

```bash
python setup_db.py
```

Existing databases should be backed up before running migrations or updating the application.

### 7. Launch Cultiva

Start the application:

```bash
python app.py
```

## Database Information

Cultiva uses MySQL to store application records and maintain relationships between its modules.

The application includes database migration support intended to preserve existing records while introducing new features and database structures.

**Important:** Always create a database backup before installing an updated version or running a migration.

## Import System

Cultiva's Universal Multi-Module Import System supports importing records into the application's existing modules.

Supported formats include:

- CSV
- XLSX
- XLS

Imported records undergo validation before being added to the database. Related records must satisfy the application's existing relationship requirements.

The Library also supports storing other supported file types as resources.

## Notes and Limitations

- MySQL Server must be running before using database-dependent features.
- Database credentials must be configured locally.
- Imported executable files and script extensions are not executed.
- File uploads are subject to the application's existing size restrictions.
- Some file previews depend on installed Python dependencies.
- Existing database structures and records should be backed up before updates.

## Project Structure

The project is organized around its Python application files, database configuration, supporting modules, and resource management components.

Refer to the source folders for the implementation of individual features.

## Developer

**Cultiva**

Developed as a farm and garden management application using Python, Tkinter, and MySQL.

---

*Cultiva — Organize, manage, and grow.*
