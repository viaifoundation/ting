#!/usr/bin/env python3
import hmac
import http.server
import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from html import escape
from pathlib import Path
from queue_security import require_secret, validate_plan_id

PORT = 8080
SECRET_TOKEN = require_secret()
REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("TING_QUEUE_DB", str(REPO_ROOT / "queue.db"))
MAX_BODY_BYTES = 16384


@contextmanager
def queue_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db():
    with queue_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_id TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending', 'running', 'completed', 'failed')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT
            )
        """)


class WebhookHandler(http.server.BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'")
        super().end_headers()

    def respond(self, status, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def check_auth(self):
        header = self.headers.get("Authorization", "")
        if not hmac.compare_digest(header.encode("utf-8"), f"Bearer {SECRET_TOKEN}".encode("ascii")):
            self.respond(401, {"error": "Unauthorized"})
            return False
        return True

    def read_payload(self):
        if self.headers.get("Transfer-Encoding"):
            raise ValueError("Transfer-Encoding is not supported")
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= MAX_BODY_BYTES:
            raise ValueError("Request body must be between 1 and 16384 bytes")
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise ValueError("Incomplete request body")
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Expected a JSON object")
        return payload

    def do_GET(self):
        if not self.check_auth():
            return
        try:
            self.handle_get()
        except Exception:
            logging.exception("Queue GET failed")
            self.respond(500, {"error": "Internal server error"})

    def handle_get(self):
        if self.path in ("/", "/status"):
            with queue_db() as conn:
                rows = conn.execute("SELECT id, plan_id, status, created_at, started_at, completed_at, error_message FROM jobs ORDER BY id DESC LIMIT 50").fetchall()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Ting Bible Task Queue</title>
                <style>
                    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 30px; background: #f9f9fb; color: #1e1e2f; }
                    h1 { color: #4f46e5; }
                    table { width: 100%; border-collapse: collapse; margin-top: 20px; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
                    th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #e5e7eb; }
                    th { background-color: #f3f4f6; font-weight: 600; color: #4b5563; }
                    tr:hover { background-color: #f9fafb; }
                    .badge { display: inline-block; padding: 4px 8px; border-radius: 9999px; font-size: 0.75rem; font-weight: 500; text-transform: uppercase; }
                    .badge-pending { background-color: #fef3c7; color: #d97706; }
                    .badge-running { background-color: #dbeafe; color: #2563eb; }
                    .badge-completed { background-color: #d1fae5; color: #059669; }
                    .badge-failed { background-color: #fee2e2; color: #dc2626; }
                    .error { color: #dc2626; font-size: 0.85rem; font-family: monospace; white-space: pre-wrap; word-break: break-all; }
                </style>
                <meta http-equiv="refresh" content="5">
            </head>
            <body>
                <h1>Ting Bible Job Queue Monitor</h1>
                <p>Status dashboard. Auto-refreshes every 5 seconds.</p>
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Plan ID</th>
                            <th>Status</th>
                            <th>Queued At</th>
                            <th>Started At</th>
                            <th>Completed At</th>
                            <th>Details / Errors</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            if not rows:
                html += "<tr><td colspan='7' style='text-align: center; color: #9ca3af;'>No jobs in the queue.</td></tr>"
            for row in rows:
                jid, plan_id, status, created, started, completed, err = (
                    escape(str(value), quote=True) if value is not None else "" for value in row
                )
                started_str = started if started else "-"
                completed_str = completed if completed else "-"
                err_str = f"<span class='error'>{err}</span>" if err else "-"
                
                html += f"""
                <tr>
                    <td>{jid}</td>
                    <td><strong>{plan_id}</strong></td>
                    <td><span class="badge badge-{status}">{status}</span></td>
                    <td>{created} UTC</td>
                    <td>{started_str}</td>
                    <td>{completed_str}</td>
                    <td>{err_str}</td>
                </tr>
                """
            html += """
                    </tbody>
                </table>
            </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return
            
        elif self.path == "/queue":
            with queue_db() as conn:
                rows = conn.execute("SELECT id, plan_id, status FROM jobs WHERE status IN ('pending', 'running') ORDER BY id ASC").fetchall()
            self.respond(200, [{"id": r[0], "plan_id": r[1], "status": r[2]} for r in rows])
        elif self.path == "/api/next-job":
            with queue_db() as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute("SELECT id, plan_id FROM jobs WHERE status = 'pending' ORDER BY id ASC LIMIT 1").fetchone()
                if row:
                    job_id, plan_id = row
                    conn.execute("UPDATE jobs SET status = 'running', started_at = datetime('now') WHERE id = ?", (job_id,))
            self.respond(200, {"status": "running", "id": job_id, "plan_id": plan_id} if row else {"status": "idle"})
        else:
            self.respond(404, {"error": "Not Found"})

    def do_POST(self):
        if not self.check_auth():
            return
        try:
            payload = self.read_payload()
            if self.path == "/webhook":
                plan_id = validate_plan_id(payload.get("plan_id"))
                with queue_db() as conn:
                    cursor = conn.execute("INSERT INTO jobs (plan_id, status) VALUES (?, 'pending')", (plan_id,))
                    job_id = cursor.lastrowid
                self.respond(201, {"status": "queued", "job_id": job_id, "plan_id": plan_id})
            elif self.path == "/api/update-job":
                job_id = payload.get("job_id")
                status = payload.get("status")
                err_msg = payload.get("error_message")
                if type(job_id) is not int or job_id <= 0 or status not in ("completed", "failed"):
                    raise ValueError("Expected a positive integer job_id and completed or failed status")
                if err_msg is not None and (not isinstance(err_msg, str) or len(err_msg) > 4096):
                    raise ValueError("error_message must be a string of at most 4096 characters")
                with queue_db() as conn:
                    conn.execute("UPDATE jobs SET status = ?, completed_at = datetime('now'), error_message = ? WHERE id = ?", (status, err_msg, job_id))
                self.respond(200, {"status": "updated"})
            else:
                self.respond(404, {"error": "Not Found"})
        except (ValueError, UnicodeError):
            self.close_connection = True
            self.respond(400, {"error": "Invalid request body or fields"})
        except Exception:
            logging.exception("Queue POST failed")
            self.respond(500, {"error": "Internal server error"})


if __name__ == "__main__":
    init_db()
    host = os.environ.get("TING_LISTEN_HOST", "127.0.0.1")
    server = http.server.ThreadingHTTPServer((host, PORT), WebhookHandler)
    print(f"Queue Manager listening on {host}:{PORT}...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
