from datetime import date, datetime
from decimal import Decimal
import os
import mysql.connector
from mysql.connector import Error
from config import Config


def _build_mysql_connect_kwargs(user: str, password: str) -> dict:
    """Validate required MySQL connection settings and build connector kwargs."""
    host = (Config.DB_HOST or "").strip()
    database = (Config.DB_NAME or "").strip()
    username = (user or "").strip()

    if not host or not username or not database:
        raise ValueError(
            "MySQL configuration is incomplete. Set DB_HOST, DB_PORT, DB_USER, "
            "DB_PASSWORD, and DB_NAME in environment variables."
        )

    if os.environ.get("VERCEL") and host.lower() in ("localhost", "127.0.0.1", "::1"):
        raise ValueError(
            "DB_HOST cannot be 'localhost' on Vercel. Configure a remote cloud MySQL host "
            "in Vercel Environment Variables."
        )

    kwargs = {
        "host": host,
        "port": Config.DB_PORT,
        "user": username,
        "password": password or "",
        "database": database,
        "connection_timeout": 5,
    }

    ssl_mode = (getattr(Config, "DB_SSL_MODE", "") or "").strip().upper()
    ssl_ca = (getattr(Config, "DB_SSL_CA", "") or "").strip()
    if ssl_mode == "DISABLED":
        kwargs["ssl_disabled"] = True
    elif ssl_mode in ("REQUIRED", "VERIFY_CA", "VERIFY_IDENTITY"):
        kwargs["ssl_disabled"] = False
        kwargs["ssl_verify_cert"] = ssl_mode in ("VERIFY_CA", "VERIFY_IDENTITY")
        kwargs["ssl_verify_identity"] = ssl_mode == "VERIFY_IDENTITY"
    if ssl_ca:
        kwargs["ssl_ca"] = ssl_ca

    return kwargs


def get_db_connection():
    """Create and return a new MySQL database connection using Config settings."""
    kwargs = _build_mysql_connect_kwargs(Config.DB_USER, Config.DB_PASSWORD)
    return mysql.connector.connect(**kwargs)


def get_readonly_db_connection():
    """
    Create and return a MySQL connection using the dedicated read-only account.
    Raises ValueError if read-only credentials are not configured in environment variables.
    """
    ro_user = (Config.DB_READONLY_USER or "").strip()
    ro_password = Config.DB_READONLY_PASSWORD or ""

    if not ro_user or not ro_password or ro_password in (
        "your_readonly_mysql_password",
        "CHANGE_ME_STRONG_PASSWORD",
    ):
        raise ValueError(
            "Read-only MySQL account is not configured. Run create_readonly_user.sql "
            "manually and set DB_READONLY_USER and DB_READONLY_PASSWORD in environment variables."
        )

    kwargs = _build_mysql_connect_kwargs(ro_user, ro_password)
    return mysql.connector.connect(**kwargs)


def get_history_db_connection():
    """
    Create and return a MySQL connection using the dedicated query-history account
    (limited to SELECT, INSERT, UPDATE on college_db.query_history).
    Raises ValueError if history credentials are not configured in environment variables.
    """
    hist_user = (Config.DB_HISTORY_USER or "").strip()
    hist_password = Config.DB_HISTORY_PASSWORD or ""

    if not hist_user or not hist_password or hist_password in (
        "your_history_mysql_password",
        "CHANGE_ME_HISTORY_PASSWORD",
    ):
        raise ValueError(
            "Query history MySQL account is not configured. Run create_history_user.sql "
            "manually and set DB_HISTORY_USER and DB_HISTORY_PASSWORD in environment variables."
        )

    kwargs = _build_mysql_connect_kwargs(hist_user, hist_password)
    return mysql.connector.connect(**kwargs)


def close_db_connection(connection, cursor=None):
    """Safely close a MySQL cursor and connection if they are open."""
    if cursor is not None:
        try:
            cursor.close()
        except Error:
            pass

    if connection is not None:
        try:
            if connection.is_connected():
                connection.close()
        except Error:
            pass


def _serialize_value(value):
    """Convert MySQL column values into JSON-serializable Python types."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    return value


def check_db_connection():
    """Verify whether the Flask app can connect to the configured MySQL database."""
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT DATABASE()")
        row = cursor.fetchone()
        active_db = row[0] if row and row[0] else Config.DB_NAME
        return {
            "connected": True,
            "database": active_db,
            "message": f"Connected to MySQL database '{active_db}'.",
        }
    except (Error, ValueError) as err:
        return {
            "connected": False,
            "database": Config.DB_NAME or "Not configured",
            "error": str(err),
        }
    finally:
        close_db_connection(connection, cursor)


def get_database_schema():
    """
    Dynamically inspect the configured MySQL database via INFORMATION_SCHEMA
    and return tables, columns, data types, primary keys, and foreign keys.
    """
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Fetch all base tables in the target database
        cursor.execute(
            """
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
            """,
            (Config.DB_NAME,),
        )
        table_rows = cursor.fetchall()
        table_names = [row["TABLE_NAME"] for row in table_rows]

        # Fetch all column metadata for the target database
        cursor.execute(
            """
            SELECT
                TABLE_NAME,
                COLUMN_NAME,
                DATA_TYPE,
                COLUMN_TYPE,
                IS_NULLABLE,
                COLUMN_KEY
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s
            ORDER BY TABLE_NAME, ORDINAL_POSITION
            """,
            (Config.DB_NAME,),
        )
        column_rows = cursor.fetchall()

        # Fetch all foreign key relationships for the target database
        cursor.execute(
            """
            SELECT
                TABLE_NAME,
                COLUMN_NAME,
                REFERENCED_TABLE_NAME,
                REFERENCED_COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = %s
              AND REFERENCED_TABLE_NAME IS NOT NULL
            ORDER BY TABLE_NAME, ORDINAL_POSITION
            """,
            (Config.DB_NAME,),
        )
        fk_rows = cursor.fetchall()

        # Index foreign keys by (table_name, column_name)
        fk_lookup = {}
        fks_by_table = {name: [] for name in table_names}
        for fk in fk_rows:
            t_name = fk["TABLE_NAME"]
            c_name = fk["COLUMN_NAME"]
            ref = {
                "column": c_name,
                "references_table": fk["REFERENCED_TABLE_NAME"],
                "references_column": fk["REFERENCED_COLUMN_NAME"],
            }
            fk_lookup[(t_name, c_name)] = (
                f"{fk['REFERENCED_TABLE_NAME']}.{fk['REFERENCED_COLUMN_NAME']}"
            )
            if t_name in fks_by_table:
                fks_by_table[t_name].append(ref)

        # Group columns and primary keys per table
        columns_by_table = {name: [] for name in table_names}
        pks_by_table = {name: [] for name in table_names}

        for col in column_rows:
            t_name = col["TABLE_NAME"]
            c_name = col["COLUMN_NAME"]
            is_pk = col["COLUMN_KEY"] == "PRI"
            fk_target = fk_lookup.get((t_name, c_name))

            if is_pk and t_name in pks_by_table:
                pks_by_table[t_name].append(c_name)

            if t_name in columns_by_table:
                columns_by_table[t_name].append(
                    {
                        "name": c_name,
                        "data_type": col["DATA_TYPE"],
                        "column_type": col["COLUMN_TYPE"],
                        "nullable": col["IS_NULLABLE"] == "YES",
                        "is_primary_key": is_pk,
                        "is_foreign_key": fk_target is not None,
                        "references": fk_target,
                    }
                )

        tables = [
            {
                "name": name,
                "primary_keys": pks_by_table.get(name, []),
                "foreign_keys": fks_by_table.get(name, []),
                "columns": columns_by_table.get(name, []),
            }
            for name in table_names
        ]

        return {
            "database": Config.DB_NAME,
            "tables": tables,
        }
    finally:
        close_db_connection(connection, cursor)


def get_table_records(table_name, limit=100):
    """
    Fetch records from a validated table in the configured database.
    Validates table_name against INFORMATION_SCHEMA to prevent SQL injection.
    """
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        # Verify that the requested table exists in the configured database
        cursor.execute(
            """
            SELECT TABLE_NAME
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE' AND TABLE_NAME = %s
            """,
            (Config.DB_NAME, table_name),
        )
        matched = cursor.fetchone()
        if not matched:
            raise ValueError(f"Table '{table_name}' does not exist in database '{Config.DB_NAME}'.")

        safe_table = matched[0]
        safe_limit = max(1, min(int(limit), 500))

        # Safe identifier interpolation after strict INFORMATION_SCHEMA validation
        cursor.execute(f"SELECT * FROM `{safe_table}` LIMIT %s", (safe_limit,))
        column_names = list(cursor.column_names)
        raw_rows = cursor.fetchall()

        rows = [
            [_serialize_value(cell) for cell in row]
            for row in raw_rows
        ]

        return {
            "database": Config.DB_NAME,
            "table": safe_table,
            "columns": column_names,
            "rows": rows,
            "row_count": len(rows),
        }
    finally:
        close_db_connection(connection, cursor)
