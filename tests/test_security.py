import contextlib
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import queue_security

SECRET = 'test-secret-' + 'a' * 32
with patch.dict(os.environ, {'VPS_WEBHOOK_SECRET': SECRET}):
    import vps_listener as listener
    import vps_worker as worker


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_patch = patch.object(listener, 'DB_PATH', str(Path(self.tmp.name) / 'queue.db'))
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        listener.init_db()

    def request(self, method, path, payload=None, auth=True, headers=None, raw=None):
        handler = object.__new__(listener.WebhookHandler)
        body = raw if raw is not None else json.dumps(payload).encode()
        handler.path = path
        handler.headers = {'Content-Length': str(len(body))}
        if auth:
            handler.headers['Authorization'] = 'Bearer ' + SECRET
        handler.headers.update(headers or {})
        handler.rfile = io.BytesIO(body)
        handler.wfile = io.BytesIO()
        statuses = []
        handler.send_response = statuses.append
        handler.send_header = lambda *a: None
        handler.end_headers = lambda: None
        getattr(handler, 'do_' + method)()
        return statuses[-1], handler.wfile.getvalue().decode()

    def test_secret_required(self):
        for value in ('', 'change-me-securely', 'short', 'a' * 31, 'é' * 32, 'a' * 257, 'a' * 32 + '\r\n', 'a' * 16 + ' ' + 'b' * 16):
            with self.subTest(value=value), patch.dict(os.environ, {'VPS_WEBHOOK_SECRET': value}):
                with self.assertRaises(ValueError):
                    queue_security.require_secret()
        with patch.dict(os.environ, {'VPS_WEBHOOK_SECRET': SECRET}):
            self.assertEqual(queue_security.require_secret(), SECRET)

    def test_every_endpoint_requires_auth(self):
        for method, path in [('GET', '/'), ('GET', '/status'), ('GET', '/queue'), ('GET', '/api/next-job'), ('POST', '/webhook'), ('POST', '/api/update-job')]:
            with self.subTest(path=path):
                self.assertEqual(self.request(method, path, auth=False)[0], 401)
                self.assertEqual(self.request(method, path, headers={'Authorization': 'Bearer change-me-securely'})[0], 401)

    def test_reject_malicious_plan_ids_without_sql_or_generation(self):
        for plan_id in ("x' OR 1=1 --", '../assets', '/tmp', '--help', '<script>x</script>', None, [], 'a' * 129):
            with self.subTest(plan_id=plan_id):
                self.assertEqual(self.request('POST', '/webhook', {'plan_id': plan_id})[0], 400)
                with patch.object(worker.subprocess, 'run') as run, patch.object(worker, 'update_job_status') as report:
                    worker.process_job(1, plan_id)
                    run.assert_not_called()
                    report.assert_called_once_with(1, 'failed', 'Invalid plan ID')
                with patch.object(worker.subprocess, 'run') as run:
                    with self.assertRaises(ValueError):
                        worker.update_plan_status(plan_id, 'failed')
                    run.assert_not_called()

    def test_existing_plan_ids_are_accepted(self):
        root = Path(__file__).resolve().parents[1]
        for plan in (root / 'assets/bible/plans').glob('*.json'):
            self.assertEqual(queue_security.validate_plan_id(plan.stem), plan.stem)

    def test_queue_workflow(self):
        status, body = self.request('POST', '/webhook', {'plan_id': 'chronological-1year'})
        self.assertEqual(status, 201)
        job_id = json.loads(body)['job_id']
        self.assertEqual(len(json.loads(self.request('GET', '/queue')[1])), 1)
        job = json.loads(self.request('GET', '/api/next-job')[1])
        self.assertEqual(job['plan_id'], 'chronological-1year')
        self.assertEqual(json.loads(self.request('GET', '/api/next-job')[1]), {'status': 'idle'})
        self.assertEqual(self.request('POST', '/api/update-job', {'job_id': job_id, 'status': 'completed'})[0], 200)
        self.assertEqual(json.loads(self.request('GET', '/queue')[1]), [])

    def test_legacy_html_and_errors_escaped(self):
        marker = '<script>alert("x")</script>'
        with sqlite3.connect(listener.DB_PATH) as conn:
            conn.execute("INSERT INTO jobs (plan_id, status, error_message) VALUES (?, 'failed', ?)", (marker, marker))
        status, body = self.request('GET', '/status')
        self.assertEqual(status, 200)
        self.assertNotIn(marker, body)
        self.assertEqual(body.count('&lt;script&gt;'), 2)

    def test_bad_json_and_body_limits(self):
        for raw, headers in [(b'{', {}), (b'[]', {}), (b'null', {}), (b'\xff', {}), (b'{}', {'Content-Length': '-1'}), (b'{}', {'Content-Length': '999999999'}), (b'{}', {'Content-Length': 'abc'}), (b'{}', {'Content-Length': '3'}), (b'{}', {'Transfer-Encoding': 'chunked'})]:
            with self.subTest(raw=raw, headers=headers):
                self.assertEqual(self.request('POST', '/webhook', raw=raw, headers=headers)[0], 400)

    def test_update_validation(self):
        for payload in ({'job_id': True, 'status': 'failed'}, {'job_id': 1, 'status': []}, {'job_id': 1, 'status': 'pending'}, {'job_id': 1, 'status': 'failed', 'error_message': {}}, {'job_id': 1, 'status': 'failed', 'error_message': 'x' * 4097}):
            self.assertEqual(self.request('POST', '/api/update-job', payload)[0], 400)

    def test_internal_errors_not_returned(self):
        with patch.object(listener.sqlite3, 'connect', side_effect=RuntimeError('PRIVATE_PATH')), patch.object(listener.logging, 'exception'):
            status, body = self.request('GET', '/status')
        self.assertEqual(status, 500)
        self.assertNotIn('PRIVATE_PATH', body)

    def test_failure_does_not_publish_traceback(self):
        with patch.object(worker, 'generate_and_upload', side_effect=RuntimeError('PRIVATE_PATH')), patch.object(worker, 'update_job_status') as report, patch.object(worker, 'update_plan_status') as update, contextlib.redirect_stderr(io.StringIO()):
            worker.process_job(1, 'chronological-1year')
        self.assertNotIn('PRIVATE_PATH', report.call_args.args[2])
        update.assert_called_once_with('chronological-1year', 'failed', check=False)

    def test_status_update_only_changes_target(self):
        with patch.object(worker.subprocess, 'run') as run:
            worker.update_plan_status('plan-1', 'approved')
        cmd = run.call_args.args[0]
        sql = cmd[cmd.index('--command') + 1]
        with sqlite3.connect(':memory:') as conn:
            conn.execute('CREATE TABLE reading_plans (id TEXT, status TEXT)')
            conn.executemany('INSERT INTO reading_plans VALUES (?, ?)', [('plan-1', 'pending'), ('plan-2', 'pending')])
            conn.execute(sql)
            self.assertEqual(conn.execute('SELECT status FROM reading_plans ORDER BY id').fetchall(), [('approved',), ('pending',)])
        with self.assertRaises(ValueError):
            worker.update_plan_status('plan-1', "failed'; DROP TABLE reading_plans; --")

    def test_symlink_audio_directory_rejected(self):
        root = Path(self.tmp.name)
        (root / 'audio').mkdir()
        (root / 'audio' / 'plan-1').symlink_to(root, target_is_directory=True)
        with patch.object(worker, 'REPO_ROOT', root), self.assertRaises(ValueError):
            worker.plan_audio_dir('plan-1')

    def test_transport_requires_https_off_loopback(self):
        for url in ('http://example.com', 'ftp://example.com', 'https://user:pass@example.com', 'https://example.com/?secret=x', 'https://example.com/path'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                queue_security.validate_manager_url(url)
        for url in ('http://localhost:8080', 'http://127.0.0.1:8080', 'https://example.com'):
            self.assertEqual(queue_security.validate_manager_url(url), url)

    def test_response_security_headers(self):
        handler = object.__new__(listener.WebhookHandler)
        handler.request_version = "HTTP/1.1"
        handler._headers_buffer = []
        handler.wfile = io.BytesIO()
        handler.end_headers()
        headers = handler.wfile.getvalue().decode()
        self.assertIn("Cache-Control: no-store", headers)
        self.assertIn("X-Content-Type-Options: nosniff", headers)
        self.assertIn("default-src 'none'", headers)
        self.assertIn("frame-ancestors 'none'", headers)

    def test_happy_path_worker_preserves_generation_and_upload(self):
        root = Path(self.tmp.name)
        (root / 'audio' / 'plan-1').mkdir(parents=True)
        with patch.object(worker, 'REPO_ROOT', root), patch.object(worker.subprocess, 'run') as run, patch('shutil.rmtree') as cleanup, contextlib.redirect_stdout(io.StringIO()):
            worker.generate_and_upload('plan-1')
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(len(commands), 6)
        self.assertTrue(all('generate_plan_audio.py' in cmd[1] for cmd in commands[:4]))
        self.assertIn('upload_to_r2.py', commands[4][1])
        self.assertIn("WHERE id = 'plan-1'", commands[5][-1])
        cleanup.assert_called_once_with((root / 'audio' / 'plan-1').resolve())

    def test_report_does_not_follow_redirects(self):
        with patch.object(worker.requests, 'post') as post:
            post.return_value.status_code = 200
            worker.update_job_status(1, 'completed')
            self.assertFalse(post.call_args.kwargs['allow_redirects'])


if __name__ == '__main__':
    unittest.main()
