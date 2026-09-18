import json
import os
import time

from common import client, emit, metric


QUEUE_URL = os.environ["QUEUE_URL"]
RESULT_TABLE = os.environ["RESULT_TABLE"]


def run():
    queue = client("sqs")
    table = client("dynamodb")
    emit("worker", "started")
    while True:
        metric("worker", "WorkerHeartbeat")
        try:
            messages = queue.receive_message(QueueUrl=QUEUE_URL, MaxNumberOfMessages=5,
                                             WaitTimeSeconds=2, VisibilityTimeout=20).get("Messages", [])
            for message in messages:
                started = time.monotonic()
                try:
                    job = json.loads(message["Body"])
                    job_id = job["job_id"]
                    trace_id = job["trace_id"]
                    table.put_item(TableName=RESULT_TABLE, Item={
                        "job_id": {"S": job_id}, "value": {"S": str(job.get("value", "ok"))},
                        "trace_id": {"S": trace_id}, "completed_at": {"N": str(int(time.time()))},
                    })
                    queue.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=message["ReceiptHandle"])
                    metric("worker", "CompletedJobs")
                    metric("worker", "ProcessingDurationMs", (time.monotonic() - started) * 1000, "Milliseconds")
                    emit("worker", "job_completed", job_id=job_id, trace_id=trace_id,
                         span_id="worker-" + job_id[:12], parent_span_id="api-" + job_id[:12])
                except Exception as exc:
                    metric("worker", "ProcessingErrors")
                    emit("worker", "job_failed", level="ERROR", error_type=type(exc).__name__)
        except Exception as exc:
            emit("worker", "poll_failed", level="ERROR", error_type=type(exc).__name__)
            time.sleep(2)


if __name__ == "__main__":
    run()
