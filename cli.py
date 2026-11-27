"""AICompanyOS entry point: command line + small JSON HTTP API (standard library only).

Examples:
    python cli.py init
    python cli.py add-task "Translate 500 words" --price 5 --source khamsat
    python cli.py tasks
    python cli.py set-status 1 classified --category translation
    python cli.py ledger income 5 --task 1 --note "client payment"
    python cli.py summary
    python cli.py backup
    python cli.py serve
"""
from __future__ import annotations

import argparse
import hmac
import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from core import agents as agents_mod
from core import backup as backup_mod
from core.logs import get_logger
from core.service import Company
from core.validator import (
    TASK_STATUSES,
    ValidationError,
)

MAX_BODY = 1_000_000  # 1 MB
LOCAL_HOSTS = ("127.0.0.1", "localhost")


# ----------------------------------------------------------------------------- HTTP

def make_handler(company: Company):
    log = get_logger("http")
    api_key = company.settings.api_key

    class Handler(BaseHTTPRequestHandler):
        server_version = "AICompanyOS"

        def log_message(self, fmt, *args):  # route access log to our logger
            log.info("%s %s", self.address_string(), fmt % args)

        def _send(self, code: int, payload) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self) -> bool:
            if not api_key:
                return True
            return hmac.compare_digest(self.headers.get("X-API-Key", ""), api_key)

        def _read_json(self) -> dict:
            raw_length = self.headers.get("Content-Length") or "0"
            try:
                length = int(raw_length)
            except (TypeError, ValueError):
                raise ValidationError("invalid Content-Length header") from None
            if length < 0:
                raise ValidationError("Content-Length must not be negative")
            if length > MAX_BODY:
                raise ValidationError("request body too large")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw or b"{}")
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise ValidationError("invalid JSON") from None
            if not isinstance(data, dict):
                raise ValidationError("JSON body must be an object")
            return data

        def _route(self, method: str) -> None:
            parts = urlsplit(self.path)
            path = parts.path.rstrip("/") or "/"
            query = parse_qs(parts.query)
            try:
                # Without an API key only local Host headers are accepted (DNS rebinding).
                host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
                if not api_key and host not in LOCAL_HOSTS:
                    return self._send(403, {"error": "forbidden host"})

                # Writes must be JSON: browsers then need a CORS preflight, which blocks
                # cross-site form posts (text/plain) to the local API.
                if method in ("POST", "PATCH"):
                    ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip()
                    if ctype.lower() != "application/json":
                        return self._send(
                            415, {"error": "Content-Type must be application/json"}
                        )

                if path == "/health" and method == "GET":
                    return self._send(200, {"status": "ok"})
                if not self._authorized():
                    return self._send(401, {"error": "invalid or missing X-API-Key"})

                if path == "/tasks" and method == "GET":
                    status = (query.get("status") or [None])[0]
                    if status is not None and status not in TASK_STATUSES:
                        raise ValidationError("invalid status")
                    return self._send(200, company.db.list_tasks(status))
                if path == "/tasks" and method == "POST":
                    return self._send(
                        201, company.add_task_analyzed(self._read_json(), user_name="api")
                    )
                m = re.fullmatch(r"/tasks/(\d+)", path)
                if m and method == "GET":
                    return self._send(200, company.db.get_task(int(m.group(1))))
                if m and method == "PATCH":
                    return self._send(200, company.update_task(m.group(1), self._read_json(), user_name="api"))
                if path == "/agents" and method == "GET":
                    return self._send(200, company.db.list_agents())
                if path == "/ledger" and method == "GET":
                    return self._send(200, company.db.list_ledger())
                if path == "/ledger" and method == "POST":
                    return self._send(
                        201, company.add_ledger(self._read_json(), user_name="api")
                    )
                if path == "/summary" and method == "GET":
                    return self._send(200, company.db.summary())
                self._send(404, {"error": "not found"})
            except ValidationError as exc:
                self._send(400, {"error": str(exc)})
            except LookupError as exc:
                self._send(404, {"error": str(exc)})
            except Exception:  # never leak internals to the client
                log.exception("unhandled error on %s %s", method, self.path)
                self._send(500, {"error": "internal server error"})

        def do_GET(self):
            self._route("GET")

        def do_POST(self):
            self._route("POST")

        def do_PATCH(self):
            self._route("PATCH")

    return Handler


def serve(company: Company) -> None:
    s = company.settings
    if s.host not in ("127.0.0.1", "localhost") and not s.api_key:
        print("Refusing to listen on a public address without an API key. "
              "Set AICOS_API_KEY or keep host=127.0.0.1.", file=sys.stderr)
        sys.exit(2)
    server = ThreadingHTTPServer((s.host, s.port), make_handler(company))
    print(f"AICompanyOS API listening on http://{s.host}:{s.port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()


# ----------------------------------------------------------------------------- CLI

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cli.py", description="Free open-source AI business OS")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create the database and default agents")

    a = sub.add_parser("add-task", help="add a task")
    a.add_argument("title")
    a.add_argument("--description", default="")
    a.add_argument("--source", default="")
    a.add_argument("--category", default="")
    a.add_argument("--price", default=0)
    a.add_argument("--currency", default="")

    t = sub.add_parser("tasks", help="list tasks")
    t.add_argument("--status", choices=TASK_STATUSES)

    s = sub.add_parser("set-status", help="change a task's status")
    s.add_argument("id")
    s.add_argument("status", choices=TASK_STATUSES)
    s.add_argument("--category")
    s.add_argument("--agent")

    l = sub.add_parser("ledger", help="record income or expense")
    l.add_argument("kind", choices=("income", "expense"))
    l.add_argument("amount")
    l.add_argument("--currency", default="")
    l.add_argument("--task")
    l.add_argument("--note", default="")

    sub.add_parser("agents", help="list agents")
    sub.add_parser("run-agents", help="run classifier and manager over new tasks")
    sub.add_parser("run-accountant", help="record income for completed tasks")
    sub.add_parser("summary", help="accounting and task summary")
    sub.add_parser("backup", help="create a database backup")

    r = sub.add_parser("restore", help="restore a database backup")
    r.add_argument("file")

    sub.add_parser("serve", help="run the JSON HTTP API")
    return p


def show(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    company = Company()
    s = company.settings
    try:
        if args.cmd == "init":
            print(f"ready: {s.db_path}")
        elif args.cmd == "add-task":
            show(company.add_task_analyzed({
                "title": args.title, "description": args.description, "source": args.source,
                "category": args.category, "price": args.price, "currency": args.currency,
            }, user_name="cli"))
        elif args.cmd == "tasks":
            show(company.db.list_tasks(args.status))
        elif args.cmd == "set-status":
            data = {"status": args.status, "category": args.category, "agent": args.agent}
            show(company.update_task(args.id, {k: v for k, v in data.items() if v is not None}, user_name="cli"))
        elif args.cmd == "ledger":
            show(company.add_ledger({
                "kind": args.kind, "amount": args.amount, "currency": args.currency,
                "task_id": args.task, "note": args.note,
            }, user_name="cli"))
        elif args.cmd == "agents":
            show(company.db.list_agents())
        elif args.cmd == "run-agents":
            show(agents_mod.run_pipeline(company.db))
        elif args.cmd == "run-accountant":
            show(agents_mod.run_accountant(company.db))
        elif args.cmd == "summary":
            show(company.db.summary())
        elif args.cmd == "backup":
            print(backup_mod.create_backup(s.db_path, s.backup_dir, s.backup_keep))
        elif args.cmd == "restore":
            backup_mod.restore_backup(args.file, s.db_path)
            print("restored")
        elif args.cmd == "serve":
            serve(company)
    except (ValidationError, LookupError, FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
