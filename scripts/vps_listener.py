#!/usr/bin/env python3
import http.server
import json
import os
import sqlite3
from pathlib import Path

PORT = 8080
SECRET_TOKEN = os.environ.get("VPS_WEBHOOK_SECRET", "change-me-securely")
REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("TING_QUEUE_DB", str(REPO_ROOT / "queue.db"))

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('pending', 'running', 'completed', 'failed')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        started_at TIMESTAMP,
        completed_at TIMESTAMP,
        error_message TEXT
    );
    """)
    conn.commit()
    conn.close()

class WebhookHandler(http.server.BaseHTTPRequestHandler):
    def check_auth(self):
        auth_header = self.headers.get("Authorization")
        if not auth_header or auth_header != f"Bearer {SECRET_TOKEN}":
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b"Unauthorized")
            return False
        return True

    def do_GET(self):
        if self.path in ("/", "/status"):
            # Output an HTML dashboard
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("SELECT id, plan_id, status, created_at, started_at, completed_at, error_message FROM jobs ORDER BY id DESC LIMIT 50")
                rows = c.fetchall()
                conn.close()
            except Exception as e:
                self.wfile.write(f"<h2>Database Error: {e}</h2>".encode("utf-8"))
                return
                
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
                jid, plan_id, status, created, started, completed, err = row
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
            # Output JSON of pending/running queue
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            try:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("SELECT id, plan_id, status FROM jobs WHERE status IN ('pending', 'running') ORDER BY id ASC")
                jobs = [{"id": r[0], "plan_id": r[1], "status": r[2]} for r in c.fetchall()]
                conn.close()
                self.wfile.write(json.dumps(jobs).encode("utf-8"))
            except Exception as e:
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        elif self.path == "/api/next-job":
            # Authentication check
            if not self.check_auth():
                return
                
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            
            try:
                # Use BEGIN IMMEDIATE transaction to prevent concurrent race conditions
                conn = sqlite3.connect(DB_PATH)
                conn.execute("BEGIN IMMEDIATE")
                c = conn.cursor()
                c.execute("SELECT id, plan_id FROM jobs WHERE status = 'pending' ORDER BY id ASC LIMIT 1")
                row = c.fetchone()
                
                if row:
                    job_id, plan_id = row
                    c.execute("UPDATE jobs SET status = 'running', started_at = datetime('now') WHERE id = ?", (job_id,))
                    conn.commit()
                    self.wfile.write(json.dumps({"status": "running", "id": job_id, "plan_id": plan_id}).encode("utf-8"))
                else:
                    conn.rollback()
                    self.wfile.write(json.dumps({"status": "idle"}).encode("utf-8"))
                conn.close()
            except Exception as e:
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return
            
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")
            
    def do_POST(self):
        if not self.check_auth():
            return

        if self.path == "/webhook":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                payload = json.loads(post_data.decode('utf-8'))
                plan_id = payload.get("plan_id")
                if not plan_id:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"Missing plan_id")
                    return

                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("INSERT INTO jobs (plan_id, status) VALUES (?, 'pending')", (plan_id,))
                job_id = c.lastrowid
                conn.commit()
                conn.close()

                self.send_response(201)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "queued",
                    "job_id": job_id,
                    "plan_id": plan_id
                }).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))
            return

        elif self.path == "/api/update-job":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                payload = json.loads(post_data.decode('utf-8'))
                job_id = payload.get("job_id")
                status = payload.get("status")
                err_msg = payload.get("error_message")
                
                if not job_id or not status:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"Missing job_id or status")
                    return

                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute(
                    "UPDATE jobs SET status = ?, completed_at = datetime('now'), error_message = ? WHERE id = ?",
                    (status, err_msg, job_id)
                )
                conn.commit()
                conn.close()

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "updated"}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode('utf-8'))
            return
            
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

if __name__ == "__main__":
    init_db()
    server = http.server.HTTPServer(('0.0.0.0', PORT), WebhookHandler)
    print(f"Queue Manager listening on port {PORT}...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
