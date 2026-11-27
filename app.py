import os
from flask import Flask, jsonify, render_template, request
from mysql.connector import Error as MySQLError
from ai_service import (
    AIServiceError,
    generate_sql_with_metadata,
    is_gemini_configured,
)
from config import Config
from database import check_db_connection, get_database_schema, get_table_records
from history_service import (
    HistoryServiceError,
    get_query_history,
    get_query_history_item,
    save_query_history,
    update_query_history_status,
)
from query_executor import QueryExecutorError, execute_readonly_query


def create_app() -> Flask:
    """Create and configure the Flask WSGI application."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, "templates"),
        static_folder=os.path.join(base_dir, "static"),
    )
    app.config.from_object(Config)

    @app.route("/")
    def index():
        """Render the AI-Enhanced Database Query Assistant dashboard."""
        return render_template("index.html", gemini_configured=is_gemini_configured())

    @app.route("/history")
    def history_page():
        """Render the Query History page."""
        return render_template("history.html", gemini_configured=is_gemini_configured())

    @app.route("/api/db-status", methods=["GET"])
    def db_status():
        """Check MySQL connectivity and return connection status JSON."""
        status = check_db_connection()
        http_code = 200 if status["connected"] else 503
        return jsonify(status), http_code

    @app.route("/api/db/schema", methods=["GET"])
    def db_schema():
        """Return dynamic database schema (tables, columns, types, PKs, FKs)."""
        try:
            schema = get_database_schema()
            return jsonify(schema), 200
        except (MySQLError, ValueError) as err:
            return jsonify({"error": f"Failed to retrieve database schema: {err}"}), 503

    @app.route("/api/db/tables/<table_name>", methods=["GET"])
    def db_table_records(table_name):
        """Return records for a selected table in the connected MySQL database."""
        limit = request.args.get("limit", default=100, type=int)
        try:
            data = get_table_records(table_name, limit=limit)
            return jsonify(data), 200
        except MySQLError as err:
            return jsonify({"error": f"Database query failed: {err}"}), 503
        except ValueError as err:
            status_code = 503 if "configuration" in str(err).lower() or "vercel" in str(err).lower() else 404
            return jsonify({"error": str(err)}), status_code

    @app.route("/api/generate-sql", methods=["POST"])
    def generate_sql():
        """Convert a natural-language question into a validated MySQL SELECT query."""
        payload = request.get_json(silent=True) or {}
        question = payload.get("question", "")

        if not isinstance(question, str) or not question.strip():
            return jsonify({
                "success": False,
                "error": "Please enter a natural-language question.",
            }), 400

        try:
            clean_question = question.strip()
            result = generate_sql_with_metadata(clean_question)

            history_id = None
            history_saved = False
            history_warning = None
            try:
                history_id = save_query_history(clean_question, result["sql"], "Generated")
                history_saved = True
            except HistoryServiceError as hist_err:
                history_warning = hist_err.message

            response_body = {
                "success": True,
                "question": clean_question,
                "sql": result["sql"],
                "model": result["model"],
                "fallback_used": result["fallback_used"],
                "history_id": history_id,
                "history_saved": history_saved,
            }
            if history_warning:
                response_body["history_warning"] = history_warning

            return jsonify(response_body), 200
        except AIServiceError as err:
            return jsonify({
                "success": False,
                "error": err.message,
            }), err.status_code

    @app.route("/api/execute-sql", methods=["POST"])
    def execute_sql():
        """Validate and execute a read-only SELECT query against MySQL."""
        payload = request.get_json(silent=True) or {}
        sql = payload.get("sql", "")
        question = payload.get("question", "")
        history_id = payload.get("history_id")

        if not isinstance(sql, str) or not sql.strip():
            return jsonify({
                "success": False,
                "error": "Please provide a SQL SELECT query to execute.",
            }), 400

        def _record_execution_status(status_label: str) -> tuple[int | None, bool]:
            try:
                if isinstance(history_id, int):
                    updated = update_query_history_status(history_id, status_label)
                    if updated:
                        return history_id, True
                q_text = question.strip() if isinstance(question, str) and question.strip() else "(Executed SQL Query)"
                new_id = save_query_history(q_text, sql.strip(), status_label)
                return new_id, True
            except HistoryServiceError:
                return history_id if isinstance(history_id, int) else None, False

        try:
            result = execute_readonly_query(sql)
            status_label = (
                "Empty (0 rows)"
                if result["row_count"] == 0
                else f"Success ({result['row_count']} rows)"
            )
            saved_id, history_saved = _record_execution_status(status_label)
            result["history_id"] = saved_id
            result["history_saved"] = history_saved
            return jsonify(result), 200
        except QueryExecutorError as err:
            err_prefix = "Validation Failed" if err.status_code in (400, 422) else "Execution Failed"
            saved_id, history_saved = _record_execution_status(f"{err_prefix}: {err.message}")
            return jsonify({
                "success": False,
                "error": err.message,
                "history_id": saved_id,
                "history_saved": history_saved,
            }), err.status_code

    @app.route("/api/history", methods=["GET"])
    def list_history():
        """Return saved query history records ordered by most recent first."""
        limit = request.args.get("limit", default=100, type=int)
        try:
            items = get_query_history(limit=limit)
            return jsonify({
                "success": True,
                "items": items,
                "count": len(items),
            }), 200
        except HistoryServiceError as err:
            return jsonify({
                "success": False,
                "error": err.message,
            }), err.status_code

    @app.route("/api/history/<int:history_id>", methods=["GET"])
    def history_detail(history_id):
        """Return a single query history record by ID."""
        try:
            item = get_query_history_item(history_id)
            if not item:
                return jsonify({"success": False, "error": "History entry not found."}), 404
            return jsonify({"success": True, "item": item}), 200
        except HistoryServiceError as err:
            return jsonify({
                "success": False,
                "error": err.message,
            }), err.status_code

    return app


# Module-level WSGI application instance detected by Vercel Python runtime
app = create_app()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1")
