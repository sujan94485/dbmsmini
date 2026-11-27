# AI-Enhanced Database Query Assistant

A college Database Management Systems (DBMS) mini project built with **Python Flask**, **MySQL 8.0**, **HTML/CSS/JavaScript**, **sqlglot**, and the **Google Gemini API** (`google-genai`). Users can ask questions about a college database in plain English, generate validated MySQL `SELECT` queries with Gemini AI, execute them safely using a read-only MySQL user, inspect live table schemas in a Database Explorer, review/reuse past queries in Query History, and export results to CSV.

---

## 1. Project Introduction

Relational databases power academic, enterprise, and administrative systems, yet querying them requires knowledge of SQL syntax and table relationships. **AI-Enhanced Database Query Assistant** bridges that gap by turning natural-language questions into read-only SQL queries grounded in the live database schema, validating every query before execution, and presenting results cleanly in a web dashboard.

---

## 2. Problem Statement

Non-technical users (students, faculty coordinators, and administrators) often struggle to write multi-table `JOIN`s, `GROUP BY` aggregations, and subqueries to extract insights from relational databases. Giving raw SQL access or AI-generated SQL directly to an administrative database account also introduces severe risks such as accidental `DROP`/`DELETE` statements, SQL injection, and runaway queries.

---

## 3. Project Objectives

1. Provide a clean web dashboard for entering natural-language database questions.
2. Dynamically inspect MySQL metadata (`INFORMATION_SCHEMA`) for tables, columns, data types, primary keys, and foreign keys.
3. Convert natural-language questions into valid MySQL 8.0 `SELECT` queries using Google Gemini AI.
4. Enforce strict AST-level SQL validation (`sqlglot`) and least-privilege MySQL execution using a dedicated read-only user.
5. Persist and display query history using a dedicated scoped MySQL history account, with one-click question reuse.
6. Support safe client-side CSV export with spreadsheet formula-injection protection.

---

## 4. Technologies Used

- **Backend:** Python 3.13, Flask
- **Database:** MySQL 8.0, `mysql-connector-python`
- **AI SDK:** Google Gen AI Python SDK (`google-genai`, Interactions API `client.interactions.create()`)
- **SQL Parser & Validator:** `sqlglot` (MySQL dialect AST parsing)
- **Configuration:** `python-dotenv` (`.env`)
- **Frontend:** Semantic HTML5, CSS3, Vanilla JavaScript (`fetch` API, Blob CSV download)

---

## 5. System Architecture

```text
+------------------------------------------------------------------+
|                        Browser Dashboard                         |
|  - Natural Language Input & Sample Prompts                       |
|  - Generated SQL Preview & Execute Query                         |
|  - Query Results Table & Safe CSV Export (client-side)           |
|  - Live Database Explorer & Query History Page (/history)        |
+---------------------------------+--------------------------------+
                                  | HTTP / JSON
                                  v
+------------------------------------------------------------------+
|                      Python Flask Backend                        |
|  app.py -> Routes: /, /history, /api/db-status, /api/db/schema,  |
|            /api/db/tables/<table>, /api/generate-sql,            |
|            /api/execute-sql, /api/history                        |
+--------+-------------------------+--------------------+----------+
         |                         |                    |
         v                         v                    v
+-------------------+   +---------------------+   +----------------+
|   ai_service.py   |   |  query_executor.py  |   |history_service |
| - Live schema     |   | - sqlglot MySQL AST |   | - INSERT/SELECT|
| - Gemini SDK      |   | - Read-only checks  |   |   /UPDATE on   |
| - Retry & fallback|   | - Timeout & row cap |   |   query_history|
+--------+----------+   +----------+----------+   +-------+--------+
         |                         |                      |
         v                         v                      v
+-------------------+   +------------------------------------------+
| Google Gemini API |   |          MySQL 8.0 (college_db)          |
| (Developer API)   |   |  - Admin/Explorer account (DB_USER)      |
+-------------------+   |  - Read-only account (DB_READONLY_USER)  |
                        |  - History account (DB_HISTORY_USER)     |
                        +------------------------------------------+
```

---

## 6. Python Module Guide (Beginner-Friendly)

- **`app.py`**: The main Flask entry point. It creates the Flask app, serves the HTML pages (`/` and `/history`), and exposes JSON API endpoints for database status, schema exploration, AI SQL generation, read-only SQL execution, and query history.
- **`config.py`**: Loads environment variables from `.env` using `python-dotenv` so sensitive passwords and API keys stay outside Python source files.
- **`database.py`**: Manages MySQL connections (`get_db_connection`, `get_readonly_db_connection`, `get_history_db_connection`), safe connection closing, JSON value serialization, and `INFORMATION_SCHEMA` queries for the Database Explorer.
- **`ai_service.py`**: Connects to the Google Gemini Developer API using `google-genai`, formats the live MySQL schema into the AI prompt, implements bounded exponential backoff (`1s`, `2s`, `4s` + `Retry-After`) and fallback model handling, and performs initial `SELECT`-only cleanup.
- **`query_executor.py`**: Uses `sqlglot` to parse SQL into an Abstract Syntax Tree (AST), blocks unsafe statements/functions, executes validated queries through the read-only MySQL user with a timeout and row limit, and returns structured rows and execution time.
- **`history_service.py`**: Saves newly generated queries, updates execution status after execution, and fetches past queries (newest first) from `college_db.query_history` using the dedicated history account.

---

## 7. Database Schema & Relationships (`college_db`)

The sample database `college_db` is defined in `database.sql` and contains six tables:

| Table | Description | Primary Key | Foreign Keys |
| :--- | :--- | :--- | :--- |
| `departments` | Academic departments and Heads of Department (`hod_name`) | `department_id` | — |
| `students` | Student details (`student_name`, `email`, `gender`, `admission_year`) | `student_id` | `department_id` -> `departments.department_id` |
| `courses` | Courses offered per department with credit values | `course_id` | `department_id` -> `departments.department_id` |
| `enrollments` | Student course enrollments with `marks` and `semester` | `enrollment_id` | `student_id` -> `students.student_id`, `course_id` -> `courses.course_id` |
| `faculty` | Faculty members and their designations | `faculty_id` | `department_id` -> `departments.department_id` |
| `query_history` | Saved NL questions, generated SQL, execution status, and `created_at` | `history_id` | — |

---

## 8. How Gemini AI Converts Natural Language into SQL

1. When you click **Generate SQL**, `POST /api/generate-sql` sends your question to `ai_service.py`.
2. `ai_service.py` dynamically calls `get_database_schema()` so Gemini sees the actual tables, column names, types, primary keys, and foreign-key relationships—never hardcoded schema text.
3. Gemini is called via `client.interactions.create()` with strict system instructions to output a single MySQL 8.0 `SELECT` query without explanations or modifying statements.
4. If the primary model (`GEMINI_MODEL`, default `gemini-3.8-flash`) returns HTTP `503` (overloaded), `ai_service.py` retries with bounded exponential backoff (`1s`, `2s`, `4s`), respects `Retry-After` headers, and falls back to `GEMINI_FALLBACK_MODEL` (`gemini-3.5-flash-lite`) if configured.
5. `clean_and_validate_sql()` strips any Markdown code fences and rejects non-`SELECT` or multi-statement outputs before returning SQL to the browser.

---

## 9. SQL Validation and Execution Process

Generated SQL is **never** executed automatically upon generation and is **never** trusted from the frontend without re-validation:

1. Clicking **Execute Query** sends the SQL to `POST /api/execute-sql`.
2. `query_executor.py` parses the SQL using `sqlglot.parse(..., read="mysql")`.
3. It verifies there is exactly **one** statement whose AST root is `Select` or `Union` (supporting `JOIN`s, `GROUP BY`, `ORDER BY`, aggregates, subqueries, and `WITH` CTEs).
4. Walking the entire AST, it rejects `Insert`, `Update`, `Delete`, `Drop`, `Alter`, `Create`, `TruncateTable`, `Grant`, `Revoke`, `Lock` (`FOR UPDATE`, `LOCK IN SHARE MODE`), `Into` (`INTO OUTFILE`, `INTO DUMPFILE`), and dangerous functions (`SLEEP()`, `BENCHMARK()`, `LOAD_FILE()`, `GET_LOCK()`, etc.).
5. The query runs via the read-only MySQL account with `SET SESSION MAX_EXECUTION_TIME` (`QUERY_TIMEOUT_MS`, default `5000` ms) and fetches up to `MAX_QUERY_ROWS` (default `200` rows), reporting `truncated: true` if more rows exist.

---

## 10. Least-Privilege MySQL Accounts

- **Read-Only Execution Account (`create_readonly_user.sql`)**: Creates `'query_readonly'@'localhost'` with **only `SELECT`** permission on `college_db.*`. Even if an unexpected query bypassed application checks, MySQL itself blocks any `INSERT`, `UPDATE`, `DELETE`, or `DROP`.
- **Query History Account (`create_history_user.sql`)**: Creates `'query_history_user'@'localhost'` with **only `SELECT, INSERT, UPDATE`** privileges on `college_db.query_history`, keeping history writes isolated from `root` and from other tables.

---

## 11. Query History Functionality

- Every generated query is saved in `college_db.query_history` with status `Generated`, and its status is updated when executed (e.g., `Success (12 rows)`, `Empty (0 rows)`, or an error summary).
- Open **`/history`** (via the **Query History** sidebar link) to browse previous questions and SQL queries ordered newest-first, toggle **View SQL**, and click **Reuse Question** to send the question back to the dashboard input.

---

## 12. CSV Export Functionality

- After executing a query that returns rows, click **Export CSV** in the **Query Results** header.
- Export happens **completely in the browser** from the already displayed result set—it never re-runs the SQL query.
- Values are RFC-4180 escaped (handling commas, quotes, and newlines), UTF-8 BOM encoded for Excel compatibility, saved with a timestamped filename (`query_results_YYYY-MM-DD_HH-MM-SS.csv`), and protected against spreadsheet formula injection by prefixing cells starting with `=`, `+`, `-`, `@`, `\t`, or `\r` with `'`.

---

## 13. Installation Instructions

1. **Clone or open the project folder** (`dbms/`).
2. **Create and activate a Python virtual environment:**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
3. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```
4. **Create the MySQL database and sample records:**
   ```powershell
   & "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p < database.sql
   ```
5. **Create the read-only and query-history MySQL accounts:**
   - Edit `create_readonly_user.sql` and replace `CHANGE_ME_STRONG_PASSWORD` with a strong password.
   - Edit `create_history_user.sql` and replace `CHANGE_ME_HISTORY_PASSWORD` with a strong password.
   - Execute both scripts manually in MySQL as `root`:
   ```powershell
   & "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p < create_readonly_user.sql
   & "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p < create_history_user.sql
   ```

---

## 14. Environment Configuration

Copy `.env.example` to `.env` and fill in your values (never commit `.env`):

```env
SECRET_KEY=change-this-to-a-random-secret-key

# Primary MySQL connection (used for Database Explorer schema inspection)
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=college_db

# Read-Only MySQL User for AI Query Execution
DB_READONLY_USER=query_readonly
DB_READONLY_PASSWORD=your_readonly_mysql_password
MAX_QUERY_ROWS=200
QUERY_TIMEOUT_MS=5000

# Dedicated MySQL User for Query History
DB_HISTORY_USER=query_history_user
DB_HISTORY_PASSWORD=your_history_mysql_password

# Google Gemini API Configuration
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.8-flash
GEMINI_FALLBACK_MODEL=gemini-3.5-flash-lite
```

---

## 15. How to Run the Project

```powershell
.\venv\Scripts\python.exe app.py
```

Open `http://127.0.0.1:5000/` in your browser.

---

## 16. Example Questions to Try

1. *Show all students.*
2. *Show the top 5 students based on marks.*
3. *Count the total number of students.*
4. *Find students who scored more than 80 marks.*
5. *Show the average marks for each course.*
6. *Display the number of students in each department.*

---

## 17. Testing Instructions

Run automated unit and mocked integration tests (covering `sqlglot` AST validation, Gemini retries/fallbacks/error mapping, CSV injection sanitization, query history service, and all Flask endpoints):

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```
*(Or run the inline/ad-hoc test suite described in your verification checks, and verify live routes at `http://127.0.0.1:5000/` once `.env` and MySQL users are configured.)*
