import os
import time
import uuid

import requests

from common import client, emit, metric


BASE_URL = os.environ["PUBLIC_API_URL"].rstrip("/")
QUEUE_URL = os.environ["QUEUE_URL"]
INTERVAL = int(os.getenv("CANARY_INTERVAL_SECONDS", "15"))


def probe():
    started = time.monotonic()
    trace_id = uuid.uuid4().hex
    job_id = None
    good = False
    try:
        response = requests.post(BASE_URL + "/v1/jobs", json={"value": "probe"},
                                 headers={"X-Trace-Id": trace_id}, timeout=5)
        response.raise_for_status()
        job_id = response.json()["job_id"]
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            result = requests.get(BASE_URL + "/v1/jobs/" + job_id,
                                  headers={"X-Trace-Id": trace_id}, timeout=5)
            if result.status_code == 200 and result.json().get("value") == "probe":
                good = True
                break
            time.sleep(0.5)
    except Exception as exc:
        emit("canary", "probe_error", level="ERROR", trace_id=trace_id,
             job_id=job_id, error_type=type(exc).__name__)
    metric("canary", "JourneyTotal")
    metric("canary", "JourneyGood", int(good))
    metric("canary", "JourneyDurationMs", (time.monotonic() - started) * 1000, "Milliseconds")
    metric("canary", "CanaryHeartbeat")
    try:
        attributes = client("sqs").get_queue_attributes(
            QueueUrl=QUEUE_URL, AttributeNames=["ApproximateNumberOfMessages"]
        )["Attributes"]
        metric("canary", "QueueBacklog", int(attributes["ApproximateNumberOfMessages"]))
    except Exception as exc:
        emit("canary", "backlog_probe_error", level="ERROR", error_type=type(exc).__name__)
    emit("canary", "journey_completed", level="INFO" if good else "ERROR",
         trace_id=trace_id, job_id=job_id, good=good)


if __name__ == "__main__":
    emit("canary", "started")
    while True:
        probe()
        time.sleep(INTERVAL)
