import json
import os
import socket
import time

import boto3


REGION = os.getenv("AWS_REGION", "us-east-1")
ENDPOINT = os.getenv("AWS_ENDPOINT_URL", "http://aws:4566")
PREFIX = os.environ["RESOURCE_PREFIX"]
NAMESPACE = os.getenv("METRIC_NAMESPACE", "SignalForge/ServiceHealth")
LOG_GROUP = os.getenv("LOG_GROUP")
LOG_STREAM = socket.gethostname() + "-" + str(os.getpid())
_log_stream_ready = False


def client(service):
    return boto3.client(service, region_name=REGION, endpoint_url=ENDPOINT)


def emit(service, event, level="INFO", **fields):
    global _log_stream_ready
    record = {
        "timestamp": int(time.time() * 1000),
        "service": service,
        "deployment": PREFIX,
        "level": level,
        "event": event,
        **fields,
    }
    line = json.dumps(record, separators=(",", ":"))
    print(line, flush=True)
    if LOG_GROUP:
        try:
            logs = client("logs")
            if not _log_stream_ready:
                logs.create_log_stream(logGroupName=LOG_GROUP, logStreamName=LOG_STREAM)
                _log_stream_ready = True
            logs.put_log_events(logGroupName=LOG_GROUP, logStreamName=LOG_STREAM,
                                logEvents=[{"timestamp": record["timestamp"], "message": line}])
        except Exception:
            pass


def metric(service, name, value=1, unit="Count"):
    try:
        client("cloudwatch").put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[{
                "MetricName": name,
                "Value": float(value),
                "Unit": unit,
                "Dimensions": [
                    {"Name": "Deployment", "Value": PREFIX},
                    {"Name": "Service", "Value": service},
                ],
            }],
        )
    except Exception as exc:
        emit(service, "metric_publish_failed", level="ERROR", metric=name, error_type=type(exc).__name__)
