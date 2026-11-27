from datetime import datetime
from decimal import Decimal
import os
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from flask import Flask
import httpx2
from google.genai import _interactions_errors as ie
from mysql.connector import Error as MySQLError

from app import app
import ai_service
import database
import history_service
from query_executor import QueryValidationError, validate_readonly_sql


def _make_status_error(cls, status_code, message, headers=None):
    req = httpx2.Request("POST", "https://generativelanguage.googleapis.com/v1beta/interactions")
    resp = httpx2.Response(status_code=status_code, headers=headers or {}, request=req)
    return cls(message, response=resp, body={"error": {"message": message}})


SAMPLE_SCHEMA = {
    "database": "college_db",
    "tables": [
        {
            "name": "departments",
            "columns": [
                {"name": "department_id", "column_type": "int", "nullable": False, "is_primary_key": True, "is_foreign_key": False, "references": None},
                {"name": "department_name", "column_type": "varchar(100)", "nullable": False, "is_primary_key": False, "is_foreign_key": False, "references": None},
            ],
        },
        {
            "name": "students",
            "columns": [
                {"name": "student_id", "column_type": "int", "nullable": False, "is_primary_key": True, "is_foreign_key": False, "references": None},
                {"name": "student_name", "column_type": "varchar(100)", "nullable": False, "is_primary_key": False, "is_foreign_key": False, "references": None},
                {"name": "department_id", "column_type": "int", "nullable": False, "is_primary_key": False, "is_foreign_key": True, "references": "departments.department_id"},
            ],
        },
    ],
}


class TestQueryAssistant(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_pages_and_static_assets(self):
        with patch.object(ai_service.Config, "GEMINI_API_KEY", "AIzaSyTEST_NO_LEAK"):
            r_home = self.client.get("/")
            self.assertEqual(r_home.status_code, 200)
            html = r_home.get_data(as_text=True)
            self.assertIn("generate-sql-btn", html)
            self.assertIn("execute-sql-btn", html)
            self.assertIn("export-csv-btn", html)
            self.assertIn("Database Explorer", html)
            self.assertIn("/history", html)
            self.assertNotIn("AIzaSyTEST_NO_LEAK", html)

            r_hist = self.client.get("/history")
            self.assertEqual(r_hist.status_code, 200)
            self.assertIn("Query History", r_hist.get_data(as_text=True))
            self.assertNotIn("AIzaSyTEST_NO_LEAK", r_hist.get_data(as_text=True))

        for asset in ("/static/css/style.css", "/static/js/main.js", "/static/js/history.js"):
            with self.client.get(asset) as res:
                self.assertEqual(res.status_code, 200)

    def test_db_status_error_handling(self):
        with patch("database.get_db_connection", side_effect=MySQLError(errno=2003, msg="Connection refused")):
            r = self.client.get("/api/db-status")
            self.assertEqual(r.status_code, 503)
            self.assertFalse(r.get_json()["connected"])

    def test_generate_sql_and_history_save(self):
        fake_secret = "AIzaSyTEST_NO_LEAK"
        with patch.object(ai_service.Config, "GEMINI_API_KEY", fake_secret), \
             patch("ai_service.get_database_schema", return_value=SAMPLE_SCHEMA), \
             patch("app.save_query_history", return_value=42) as mock_save:

            # Invalid empty question -> 400
            r_bad = self.client.post("/api/generate-sql", json={"question": "   "})
            self.assertEqual(r_bad.status_code, 400)

            mock_client = MagicMock()
            mock_client.interactions.create.return_value = SimpleNamespace(
                status="completed",
                errors=None,
                output_text="SELECT * FROM students;",
            )
            with patch("ai_service.genai.Client", return_value=mock_client):
                r_ok = self.client.post("/api/generate-sql", json={"question": "Show all students."})
                self.assertEqual(r_ok.status_code, 200)
                data = r_ok.get_json()
                self.assertTrue(data["success"])
                self.assertEqual(data["sql"], "SELECT * FROM students;")
                self.assertEqual(data["history_id"], 42)
                self.assertTrue(data["history_saved"])
                self.assertNotIn(fake_secret, r_ok.get_data(as_text=True))
                mock_save.assert_called_once_with("Show all students.", "SELECT * FROM students;", "Generated")

    def test_gemini_retry_and_error_mapping(self):
        err_503 = _make_status_error(ie.InternalServerError, 503, "Overloaded")
        ok_res = SimpleNamespace(status="completed", errors=None, output_text="SELECT COUNT(*) FROM students;")

        with patch.object(ai_service.Config, "GEMINI_API_KEY", "fake-key"), \
             patch.object(ai_service.Config, "GEMINI_MODEL", "gemini-3.8-flash"), \
             patch.object(ai_service.Config, "GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite"), \
             patch("ai_service.get_database_schema", return_value=SAMPLE_SCHEMA), \
             patch("app.save_query_history", return_value=1):

            mock_client = MagicMock()
            mock_client.interactions.create.side_effect = [err_503, err_503, ok_res]
            with patch("ai_service.genai.Client", return_value=mock_client), \
                 patch("ai_service.time.sleep") as mock_sleep:
                r = self.client.post("/api/generate-sql", json={"question": "Count students"})
                self.assertEqual(r.status_code, 200)
                self.assertEqual([c.args[0] for c in mock_sleep.call_args_list], [1.0, 2.0])

            mock_client.interactions.create.side_effect = _make_status_error(ie.RateLimitError, 429, "Quota")
            with patch("ai_service.genai.Client", return_value=mock_client):
                self.assertEqual(self.client.post("/api/generate-sql", json={"question": "Count"}).status_code, 429)

    def test_sql_validation_rejects_unsafe_queries(self):
        for unsafe in (
            "DROP TABLE students;",
            "DELETE FROM students;",
            "INSERT INTO students (student_name) VALUES ('x');",
            "UPDATE students SET student_name = 'x';",
            "SELECT * FROM students; DROP TABLE students;",
            "SELECT * FROM students INTO OUTFILE '/tmp/out.csv';",
            "SELECT SLEEP(5);",
            "SELECT * FROM students FOR UPDATE;",
        ):
            with self.assertRaises(QueryValidationError):
                validate_readonly_sql(unsafe)

            r = self.client.post("/api/execute-sql", json={"sql": unsafe})
            self.assertEqual(r.status_code, 422)
            self.assertFalse(r.get_json()["success"])

    def test_execute_sql_with_mocked_readonly_db_and_empty_results(self):
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_cur = MagicMock()
        mock_cur.description = [("student_id",), ("student_name",), ("marks",)]
        mock_cur.fetchmany.return_value = [(1, "Aarav Mehta", Decimal("91.50"))]
        mock_conn.cursor.return_value = mock_cur

        with patch("query_executor.get_readonly_db_connection", return_value=mock_conn), \
             patch("app.update_query_history_status", return_value=True) as mock_update:
            r = self.client.post(
                "/api/execute-sql",
                json={"sql": "SELECT student_id, student_name, marks FROM students;", "history_id": 7},
            )
            self.assertEqual(r.status_code, 200)
            body = r.get_json()
            self.assertTrue(body["success"])
            self.assertEqual(body["row_count"], 1)
            self.assertEqual(body["rows"], [[1, "Aarav Mehta", 91.5]])
            self.assertTrue(body["history_saved"])
            mock_update.assert_called_once_with(7, "Success (1 rows)")

        # Empty result set
        mock_cur.fetchmany.return_value = []
        with patch("query_executor.get_readonly_db_connection", return_value=mock_conn), \
             patch("app.save_query_history", return_value=8) as mock_save:
            r_empty = self.client.post(
                "/api/execute-sql",
                json={"sql": "SELECT student_id FROM students WHERE 1=0;", "question": "None"},
            )
            self.assertEqual(r_empty.status_code, 200)
            self.assertEqual(r_empty.get_json()["row_count"], 0)
            mock_save.assert_called_once_with("None", "SELECT student_id FROM students WHERE 1=0;", "Empty (0 rows)")

    def test_history_endpoints_and_service(self):
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [
            {
                "history_id": 10,
                "natural_language_question": "Show all students.",
                "generated_sql": "SELECT * FROM students;",
                "execution_status": "Success (12 rows)",
                "created_at": datetime(2026, 11, 26, 21, 5, 0),
            }
        ]
        mock_conn.cursor.return_value = mock_cur

        with patch("history_service.get_history_db_connection", return_value=mock_conn):
            r = self.client.get("/api/history")
            self.assertEqual(r.status_code, 200)
            data = r.get_json()
            self.assertTrue(data["success"])
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["items"][0]["created_at"], "2026-11-26 21:05:00")

        # Missing history account configuration -> 503
        with patch.object(database.Config, "DB_HISTORY_USER", ""):
            r_err = self.client.get("/api/history")
            self.assertEqual(r_err.status_code, 503)
            self.assertFalse(r_err.get_json()["success"])

        # Single item detail & 404
        mock_cur.fetchone.return_value = None
        with patch("history_service.get_history_db_connection", return_value=mock_conn):
            r_404 = self.client.get("/api/history/999")
            self.assertEqual(r_404.status_code, 404)

    def test_vercel_wsgi_env_and_connection_cleanup(self):
        # 1. Top-level Flask WSGI instance exists
        self.assertIsInstance(app, Flask)

        # 2. Missing DB_HOST in environment -> 503 JSON, no localhost fallback
        with patch.object(database.Config, "DB_HOST", ""):
            r_missing = self.client.get("/api/db-status")
            self.assertEqual(r_missing.status_code, 503)
            self.assertFalse(r_missing.get_json()["connected"])
            self.assertIn("DB_HOST", r_missing.get_json()["error"])

            r_schema = self.client.get("/api/db/schema")
            self.assertEqual(r_schema.status_code, 503)

        # 3. VERCEL=1 rejects localhost DB_HOST
        with patch.dict(os.environ, {"VERCEL": "1"}), \
             patch.object(database.Config, "DB_HOST", "localhost"), \
             patch.object(database.Config, "DB_USER", "cloud_user"), \
             patch.object(database.Config, "DB_NAME", "college_db"):
            r_vercel_local = self.client.get("/api/db-status")
            self.assertEqual(r_vercel_local.status_code, 503)
            self.assertIn("Vercel", r_vercel_local.get_json()["error"])

        # 4. SSL config kwargs built cleanly for cloud MySQL
        with patch.object(database.Config, "DB_HOST", "cloud-mysql.example.com"), \
             patch.object(database.Config, "DB_USER", "cloud_user"), \
             patch.object(database.Config, "DB_NAME", "college_db"), \
             patch.object(database.Config, "DB_SSL_MODE", "REQUIRED"):
            kwargs = database._build_mysql_connect_kwargs("cloud_user", "secret")
            self.assertEqual(kwargs["host"], "cloud-mysql.example.com")
            self.assertFalse(kwargs["ssl_disabled"])

        # 5. Connection and cursor are closed after DB status check
        mock_conn = MagicMock()
        mock_conn.is_connected.return_value = True
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = ("college_db",)
        mock_conn.cursor.return_value = mock_cur
        with patch("database.get_db_connection", return_value=mock_conn):
            r_ok = self.client.get("/api/db-status")
            self.assertEqual(r_ok.status_code, 200)
            mock_cur.close.assert_called_once()
            mock_conn.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
