from mysql.connector import Error as MySQLError
from database import _serialize_value, close_db_connection, get_history_db_connection


class HistoryServiceError(Exception):
    """Custom exception for query history database operations."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _normalize_status(status: str) -> str:
    """Truncate execution_status to fit query_history.execution_status (VARCHAR(50))."""
    cleaned = (status or "Unknown").strip()
    return cleaned[:50]


def save_query_history(question: str, generated_sql: str, execution_status: str) -> int:
    """
    Insert a new record into college_db.query_history using the dedicated history account.
    Returns the newly created history_id.
    """
    connection = None
    cursor = None
    try:
        connection = get_history_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO query_history (natural_language_question, generated_sql, execution_status)
            VALUES (%s, %s, %s)
            """,
            (
                (question or "").strip(),
                (generated_sql or "").strip(),
                _normalize_status(execution_status),
            ),
        )
        connection.commit()
        return cursor.lastrowid
    except ValueError as err:
        raise HistoryServiceError(str(err), status_code=503) from err
    except MySQLError as err:
        raise HistoryServiceError(f"Unable to save query history: {err.msg or err}", status_code=503) from err
    finally:
        close_db_connection(connection, cursor)


def update_query_history_status(history_id: int, execution_status: str) -> bool:
    """
    Update the execution_status of an existing query_history row.
    Returns True if a row was updated, False otherwise.
    """
    connection = None
    cursor = None
    try:
        connection = get_history_db_connection()
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE query_history
            SET execution_status = %s
            WHERE history_id = %s
            """,
            (_normalize_status(execution_status), int(history_id)),
        )
        connection.commit()
        return cursor.rowcount > 0
    except ValueError as err:
        raise HistoryServiceError(str(err), status_code=503) from err
    except MySQLError as err:
        raise HistoryServiceError(f"Unable to update query history: {err.msg or err}", status_code=503) from err
    finally:
        close_db_connection(connection, cursor)


def get_query_history(limit: int = 100) -> list[dict]:
    """
    Retrieve saved query history entries ordered from most recent to oldest.
    """
    safe_limit = max(1, min(int(limit), 500))
    connection = None
    cursor = None
    try:
        connection = get_history_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                history_id,
                natural_language_question,
                generated_sql,
                execution_status,
                created_at
            FROM query_history
            ORDER BY created_at DESC, history_id DESC
            LIMIT %s
            """,
            (safe_limit,),
        )
        rows = cursor.fetchall()
        return [
            {
                "history_id": row["history_id"],
                "natural_language_question": row["natural_language_question"],
                "generated_sql": row["generated_sql"],
                "execution_status": row["execution_status"],
                "created_at": _serialize_value(row["created_at"]),
            }
            for row in rows
        ]
    except ValueError as err:
        raise HistoryServiceError(str(err), status_code=503) from err
    except MySQLError as err:
        raise HistoryServiceError(f"Unable to load query history: {err.msg or err}", status_code=503) from err
    finally:
        close_db_connection(connection, cursor)


def get_query_history_item(history_id: int) -> dict | None:
    """Retrieve a single query history record by history_id."""
    connection = None
    cursor = None
    try:
        connection = get_history_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                history_id,
                natural_language_question,
                generated_sql,
                execution_status,
                created_at
            FROM query_history
            WHERE history_id = %s
            """,
            (int(history_id),),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "history_id": row["history_id"],
            "natural_language_question": row["natural_language_question"],
            "generated_sql": row["generated_sql"],
            "execution_status": row["execution_status"],
            "created_at": _serialize_value(row["created_at"]),
        }
    except ValueError as err:
        raise HistoryServiceError(str(err), status_code=503) from err
    except MySQLError as err:
        raise HistoryServiceError(f"Unable to load query history item: {err.msg or err}", status_code=503) from err
    finally:
        close_db_connection(connection, cursor)
