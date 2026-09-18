import json
import os
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from common import client, emit, metric


QUEUE_URL = os.environ["QUEUE_URL"]
RESULT_TABLE = os.environ["RESULT_TABLE"]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        return

    def response(self, status, body):
        payload = json.dumps(body, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def route(self):
        started = time.monotonic()
        request_id = str(uuid.uuid4())
        trace_id = self.headers.get("X-Trace-Id") or uuid.uuid4().hex
        status = 500
        try:
            path = urlparse(self.path).path
            if path == "/health/live":
                status = 200
                self.response(status, {"status": "live"})
            elif path == "/health/ready":
                client("sqs").get_queue_attributes(QueueUrl=QUEUE_URL, AttributeNames=["QueueArn"])
                client("dynamodb").describe_table(TableName=RESULT_TABLE)
                status = 200
                self.response(status, {"status": "ready"})
            elif self.command == "POST" and path == "/v1/jobs":
                mode = self.headers.get("X-SignalForge-Mode", "normal")
                if mode == "slow":
                    time.sleep(1.5)
                if mode == "fail":
                    status = 503
                    self.response(status, {"error": "diagnostic dependency failure"})
                else:
                    length = min(int(self.headers.get("Content-Length", "0")), 4096)
                    raw = self.rfile.read(length) if length else b"{}"
                    body = json.loads(raw)
                    job_id = uuid.uuid4().hex
                    message = {"job_id": job_id, "trace_id": trace_id, "value": body.get("value", "ok")}
                    client("sqs").send_message(QueueUrl=QUEUE_URL, MessageBody=json.dumps(message))
                    metric("api", "AcceptedJobs")
                    emit("api", "job_accepted", request_id=request_id, trace_id=trace_id, job_id=job_id,
                         span_id="api-" + job_id[:12], parent_span_id=None)
                    status = 202
                    self.response(status, {"job_id": job_id, "trace_id": trace_id, "status": "accepted"})
            elif self.command == "GET" and path.startswith("/v1/jobs/"):
                job_id = path.removeprefix("/v1/jobs/")
                item = client("dynamodb").get_item(TableName=RESULT_TABLE, Key={"job_id": {"S": job_id}}).get("Item")
                if item:
                    status = 200
                    self.response(status, {"job_id": job_id, "status": "completed", "value": item["value"]["S"]})
                else:
                    status = 202
                    self.response(status, {"job_id": job_id, "status": "pending"})
            else:
                status = 404
                self.response(status, {"error": "not found"})
        except Exception as exc:
            status = 503
            emit("api", "request_error", level="ERROR", request_id=request_id, trace_id=trace_id,
                 error_type=type(exc).__name__)
            try:
                self.response(status, {"error": "service unavailable"})
            except Exception:
                pass
        finally:
            duration = (time.monotonic() - started) * 1000
            if not self.path.startswith("/health/"):
                metric("api", "RequestTotal")
                if status >= 500:
                    metric("api", "RequestErrors")
                metric("api", "RequestDurationMs", duration, "Milliseconds")
                emit("api", "request_completed", level="ERROR" if status >= 500 else "INFO",
                     request_id=request_id, trace_id=trace_id, method=self.command,
                     path=urlparse(self.path).path, status=status, duration_ms=round(duration, 2))

    do_GET = route
    do_POST = route


if __name__ == "__main__":
    emit("api", "started")
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
