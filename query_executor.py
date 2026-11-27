import re
import time
from mysql.connector import Error as MySQLError
import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError
from config import Config
from database import _serialize_value, close_db_connection, get_readonly_db_connection

# Dangerous MySQL functions blocked during AST inspection
DANGEROUS_FUNCTIONS = {
    "SLEEP",
    "BENCHMARK",
    "LOAD_FILE",
    "GET_LOCK",
    "RELEASE_LOCK",
    "IS_FREE_LOCK",
    "IS_USED_LOCK",
    "MASTER_POS_WAIT",
    "WAIT_FOR_EXECUTED_GTID_SET",
}

# AST node types representing disallowed write, DDL, or session commands
DISALLOWED_NODE_TYPES = tuple(
    node_cls
    for node_cls in (
        getattr(exp, "Insert", None),
        getattr(exp, "Update", None),
        getattr(exp, "Delete", None),
        getattr(exp, "Drop", None),
        getattr(exp, "Alter", None),
        getattr(exp, "Create", None),
        getattr(exp, "Command", None),
        getattr(exp, "Into", None),
        getattr(exp, "Lock", None),
        getattr(exp, "Set", None),
        getattr(exp, "Merge", None),
        getattr(exp, "TruncateTable", None),
        getattr(exp, "Grant", None),
        getattr(exp, "Revoke", None),
        getattr(exp, "Commit", None),
        getattr(exp, "Rollback", None),
        getattr(exp, "Transaction", None),
        getattr(exp, "Use", None),
    )
    if node_cls is not None
)


class QueryExecutorError(Exception):
    """Base error for SQL validation and read-only execution."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class QueryValidationError(QueryExecutorError):
    """Raised when SQL fails read-only AST validation."""


class QueryExecutionError(QueryExecutorError):
    """Raised when MySQL fails or times out while executing a validated query."""


def _strip_quoted_literals(sql: str) -> str:
    """Remove string literals and backticked identifiers for safe token checks."""
    sql = re.sub(r"'(?:\\.|''|[^'])*'", "''", sql)
    sql = re.sub(r'"(?:\\.|""|[^"])*"', '""', sql)
    sql = re.sub(r"`[^`]*`", "``", sql)
    return sql


def validate_readonly_sql(sql: str) -> str:
    """
    Validate using sqlglot (MySQL dialect) that the input is strictly a single
    read-only SELECT (or WITH/UNION SELECT) query with no dangerous clauses or functions.
    """
    if not isinstance(sql, str) or not sql.strip():
        raise QueryValidationError("Please provide a SQL query to execute.", status_code=400)

    cleaned = sql.strip()

    # Defense-in-depth check against INTO OUTFILE / INTO DUMPFILE outside string literals
    unquoted = _strip_quoted_literals(cleaned).upper()
    if re.search(r"\bINTO\s+(?:OUTFILE|DUMPFILE)\b", unquoted):
        raise QueryValidationError(
            "File export clauses (INTO OUTFILE / INTO DUMPFILE) are not permitted.",
            status_code=422,
        )

    try:
        parsed_statements = sqlglot.parse(cleaned, read="mysql")
    except ParseError as err:
        raise QueryValidationError(f"Invalid SQL syntax: {err}", status_code=400) from err

    statements = [stmt for stmt in parsed_statements if stmt is not None]

    if not statements:
        raise QueryValidationError("SQL query is empty.", status_code=400)

    if len(statements) > 1:
        raise QueryValidationError(
            "Multiple SQL statements are not allowed. Execute one SELECT query at a time.",
            status_code=422,
        )

    root = statements[0]
    if not isinstance(root, (exp.Select, exp.Union)):
        raise QueryValidationError(
            "Only SELECT queries are allowed. Modifying or administrative statements are blocked.",
            status_code=422,
        )

    # Walk the entire AST (including CTEs, subqueries, and UNION branches)
    for node in root.walk():
        if isinstance(node, DISALLOWED_NODE_TYPES):
            raise QueryValidationError(
                f"Disallowed SQL operation '{type(node).__name__}' detected. Only read-only SELECT queries are permitted.",
                status_code=422,
            )

        if isinstance(node, exp.Func):
            func_name = ""
            if isinstance(node, exp.Anonymous):
                func_name = (node.name or "").upper()
            else:
                func_name = (node.sql_name() if hasattr(node, "sql_name") else type(node).__name__).upper()

            if func_name in DANGEROUS_FUNCTIONS:
                raise QueryValidationError(
                    f"Function '{func_name}()' is blocked for security and stability reasons.",
                    status_code=422,
                )

    return cleaned


def _format_mysql_error(err: MySQLError, timeout_ms: int) -> QueryExecutionError:
    """Convert a MySQL connector error into a safe, user-friendly QueryExecutionError."""
    errno = getattr(err, "errno", None)
    msg = getattr(err, "msg", None) or str(err)

    if errno in (3024, 1317):
        return QueryExecutionError(
            f"Query execution timed out after {timeout_ms} ms. Try narrowing your query.",
            status_code=504,
        )
    if errno == 1045:
        return QueryExecutionError(
            "Read-only MySQL authentication failed. Check DB_READONLY_USER and DB_READONLY_PASSWORD in .env.",
            status_code=503,
        )
    if errno == 1142:
        return QueryExecutionError(
            "Permission denied: the read-only MySQL account can only execute SELECT queries on college_db.",
            status_code=403,
        )
    if errno in (1064, 1146, 1054, 1052, 1109, 1140, 1241, 1242):
        return QueryExecutionError(f"SQL query error: {msg}", status_code=400)
    if errno in (2002, 2003, 2005, 2006, 2013):
        return QueryExecutionError(
            "Unable to connect to the MySQL server. Ensure MySQL is running and accessible.",
            status_code=503,
        )

    return QueryExecutionError(f"Database execution error: {msg}", status_code=500)


def execute_readonly_query(
    sql: str,
    max_rows: int = None,
    timeout_ms: int = None,
) -> dict:
    """
    Validate a SQL query, execute it against MySQL using the read-only user account
    with a query timeout and row cap, and return structured results.
    """
    validated_sql = validate_readonly_sql(sql)

    effective_max_rows = max(1, int(max_rows if max_rows is not None else Config.MAX_QUERY_ROWS))
    effective_timeout_ms = max(500, int(timeout_ms if timeout_ms is not None else Config.QUERY_TIMEOUT_MS))

    connection = None
    cursor = None

    try:
        connection = get_readonly_db_connection()
        cursor = connection.cursor()

        # Apply MySQL 8.0 session-level read-only SELECT timeout in milliseconds
        try:
            cursor.execute(f"SET SESSION MAX_EXECUTION_TIME = {effective_timeout_ms}")
        except MySQLError:
            # Continue if the server/session does not support MAX_EXECUTION_TIME
            pass

        start_time = time.perf_counter()
        cursor.execute(validated_sql)

        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        fetched = cursor.fetchmany(effective_max_rows + 1)
        elapsed_seconds = round(time.perf_counter() - start_time, 4)

        truncated = len(fetched) > effective_max_rows
        limited_rows = fetched[:effective_max_rows]
        serialized_rows = [
            [_serialize_value(cell) for cell in row]
            for row in limited_rows
        ]

        # Drain any remaining buffered rows cleanly before closing cursor
        if truncated:
            try:
                cursor.fetchall()
            except MySQLError:
                pass

        return {
            "success": True,
            "columns": columns,
            "rows": serialized_rows,
            "row_count": len(serialized_rows),
            "execution_time": elapsed_seconds,
            "truncated": truncated,
            "max_rows": effective_max_rows,
        }
    except QueryExecutorError:
        raise
    except ValueError as err:
        raise QueryExecutionError(str(err), status_code=503) from err
    except MySQLError as err:
        raise _format_mysql_error(err, effective_timeout_ms) from err
    finally:
        close_db_connection(connection, cursor)
