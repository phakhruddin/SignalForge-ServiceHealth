"""Behavior-led verifier for the public SignalForge contract.

The checks use manifest IDs only as discovery hints. Terraform state and live
APIs are also read so a fabricated manifest cannot earn infrastructure points.
"""

import datetime as dt
import json
import os
import subprocess
import time
import uuid
from pathlib import Path

import boto3
import jsonschema
import requests


SUBMISSION = Path("/workspace/submission")
CONFIG = json.loads(Path("/workspace/config/config.json").read_text())
SCHEMA = json.loads(Path("/tests/contracts/manifest.schema.json").read_text())
LOG_DIR = Path("/logs/verifier")
ENDPOINT = CONFIG["aws_endpoint_url"]
REGION = CONFIG["region"]
NAMESPACE = CONFIG["metric_namespace"]
PREFIX = CONFIG["resource_prefix"]
session = boto3.Session(region_name=REGION, aws_access_key_id="test", aws_secret_access_key="test")


def cloud(name):
    return session.client(name, endpoint_url=ENDPOINT)


def eventually(fn, timeout=60, interval=2):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            value = fn()
            if value:
                return value
        except Exception as exc:
            last = exc
        time.sleep(interval)
    if last:
        raise AssertionError(f"condition did not converge: {last}")
    raise AssertionError("condition did not converge")


def dimensions(service):
    return [{"Name": "Deployment", "Value": PREFIX}, {"Name": "Service", "Value": service}]


def sample(name, service, stat="Sum"):
    end = dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=2)
    begin = end - dt.timedelta(minutes=10)
    points = cloud("cloudwatch").get_metric_statistics(
        Namespace=NAMESPACE, MetricName=name, Dimensions=dimensions(service),
        StartTime=begin, EndTime=end, Period=60, Statistics=[stat],
    )["Datapoints"]
    return sum(float(point.get(stat, 0)) for point in points)


def log_records(group):
    events = cloud("logs").filter_log_events(logGroupName=group, startTime=int((time.time() - 600) * 1000)).get("events", [])
    records = []
    for event in events:
        try:
            records.append(json.loads(event["message"]))
        except (ValueError, KeyError):
            pass
    return records


def alarm(manifest, key):
    alarms = cloud("cloudwatch").describe_alarms(AlarmNames=[manifest["alarms"][key]])["MetricAlarms"]
    assert len(alarms) == 1
    return alarms[0]


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    def check(name, points, fn):
        try:
            evidence = fn()
            results.append({"name": name, "points": points, "earned": points, "evidence": str(evidence)[:500]})
            print(f"PASS {name} ({points})", flush=True)
        except Exception as exc:
            results.append({"name": name, "points": points, "earned": 0, "error": str(exc)[:500]})
            print(f"FAIL {name} ({points}): {exc}", flush=True)

    def save():
        score = sum(result["earned"] for result in results)
        (LOG_DIR / "report.json").write_text(json.dumps({"score": score, "checks": results}, indent=2))
        (LOG_DIR / "reward.json").write_text(json.dumps({"score": score, "reward": score / 100}))
        (LOG_DIR / "reward.txt").write_text(f"{score / 100}\n")
        print(f"SignalForge score: {score}/100", flush=True)

    try:
        deploy = SUBMISSION / "deploy.sh"
        assert deploy.is_file(), "missing deploy.sh"
        run = subprocess.run([str(deploy)], cwd=SUBMISSION, capture_output=True, text=True, timeout=720)
        (LOG_DIR / "deploy.log").write_text((run.stdout + "\n" + run.stderr)[-1000000:])
        assert run.returncode == 0, f"deploy failed ({run.returncode}): {run.stderr[-1000:]}"
        manifest = json.loads((SUBMISSION / "manifest.json").read_text())
        jsonschema.validate(manifest, SCHEMA)
        assert manifest["resource_prefix"] == PREFIX
    except Exception as exc:
        results.append({"name": "deployment gate", "points": 100, "earned": 0, "error": str(exc)})
        save()
        return

    api_url = manifest["api_url"].rstrip("/")
    cw = cloud("cloudwatch")
    ecs = cloud("ecs")
    queue = cloud("sqs")
    state = json.loads(subprocess.check_output(["terraform", "-chdir=/workspace/submission/infra", "show", "-json"], text=True))
    resources = state.get("values", {}).get("root_module", {}).get("resources", [])
    types = [resource.get("type") for resource in resources]

    def declared_alarm(name):
        matches = [resource["values"] for resource in resources
                   if resource.get("type") == "aws_cloudwatch_metric_alarm"
                   and resource.get("values", {}).get("alarm_name") == name]
        assert len(matches) == 1, f"alarm {name} absent from Terraform state"
        return matches[0]

    def submit(mode=None, secret=None):
        headers = {"X-Trace-Id": uuid.uuid4().hex}
        if mode:
            headers["X-SignalForge-Mode"] = mode
        payload = {"value": "verify-" + uuid.uuid4().hex[:8]}
        if secret:
            payload["secret"] = secret
        response = requests.post(api_url + "/v1/jobs", json=payload, headers=headers, timeout=10)
        return response, headers["X-Trace-Id"], payload

    response, trace_id, payload = submit(secret="do-not-log-" + uuid.uuid4().hex)
    job_id = response.json().get("job_id") if response.status_code == 202 else None

    def completed():
        if not job_id:
            return False
        answer = requests.get(api_url + "/v1/jobs/" + job_id, timeout=5)
        return answer.status_code == 200 and answer.json().get("value") == payload["value"]

    check("api request population", 6, lambda: (
        (lambda failed, slow: (
            failed.status_code == 503 and slow.status_code == 202 and
            eventually(lambda: sample("RequestTotal", "api") >= 3) and
            eventually(lambda: sample("RequestErrors", "api") >= 1) and
            eventually(lambda: sample("RequestDurationMs", "api") >= 1000)
        ))(submit(mode="fail")[0], submit(mode="slow")[0]) or (_ for _ in ()).throw(AssertionError("API metrics/status mismatch"))
    ))
    check("worker population", 5, lambda: (
        eventually(completed, timeout=90) and eventually(lambda: sample("CompletedJobs", "worker") >= 1)
    ) or (_ for _ in ()).throw(AssertionError("job not completed or worker metric missing")))
    check("journey population", 5, lambda: eventually(lambda: sample("JourneyTotal", "canary") >= 1 and sample("JourneyGood", "canary") >= 1, timeout=90))
    check("SLI numerator and denominator", 4, lambda: (
        sample("JourneyTotal", "canary") >= sample("JourneyGood", "canary") > 0
    ) or (_ for _ in ()).throw(AssertionError("invalid journey populations")))

    check("API JSON logs", 4, lambda: eventually(lambda: any(
        r.get("event") == "request_completed" and r.get("trace_id") == trace_id and
        r.get("request_id") and isinstance(r.get("duration_ms"), (int, float))
        for r in log_records(manifest["log_groups"]["api"]))))
    check("worker JSON logs", 4, lambda: eventually(lambda: any(
        r.get("event") == "job_completed" and r.get("trace_id") == trace_id and r.get("job_id") == job_id
        for r in log_records(manifest["log_groups"]["worker"]))))
    def linked_spans():
        api_record = next((r for r in log_records(manifest["log_groups"]["api"])
                           if r.get("event") == "job_accepted" and r.get("job_id") == job_id), None)
        worker_record = next((r for r in log_records(manifest["log_groups"]["worker"])
                              if r.get("event") == "job_completed" and r.get("job_id") == job_id), None)
        return api_record and worker_record and api_record.get("trace_id") == worker_record.get("trace_id") == trace_id and worker_record.get("parent_span_id") == api_record.get("span_id")

    check("span linkage", 4, lambda: eventually(linked_spans))
    check("secret-safe logs", 3, lambda: all(
        payload["secret"] not in json.dumps(log_records(group))
        for group in manifest["log_groups"].values()
    ) or (_ for _ in ()).throw(AssertionError("secret found in logs")))

    def metric_alarm(key, metric, service, threshold):
        item = alarm(manifest, key)
        assert item.get("MetricName") == metric
        assert item.get("Namespace") == NAMESPACE
        assert {d["Name"]: d["Value"] for d in item.get("Dimensions", [])} == {d["Name"]: d["Value"] for d in dimensions(service)}
        assert float(item["Threshold"]) == threshold
        assert manifest["incident_topic_arn"] in item.get("AlarmActions", [])
        return item["AlarmName"]

    check("API error alarm", 4, lambda: metric_alarm("api_errors", "RequestErrors", "api", 1))
    check("API latency alarm", 4, lambda: metric_alarm("api_latency", "RequestDurationMs", "api", 1000))
    check("backlog alarm", 3, lambda: metric_alarm("backlog", "QueueBacklog", "canary", 1))

    def journey_alarm():
        item = alarm(manifest, "journey_failure")
        declared = declared_alarm(item["AlarmName"])
        assert manifest["incident_topic_arn"] in item.get("AlarmActions", [])
        queries = json.dumps(declared.get("metric_query", []))
        assert "JourneyGood" in queries and "JourneyTotal" in queries
        return item["AlarmName"]

    check("journey alarm", 4, journey_alarm)
    def telemetry_loss_alarm():
        name = metric_alarm("telemetry_loss", "CanaryHeartbeat", "canary", 1)
        ecs.update_service(cluster=manifest["ecs_cluster"], service=manifest["canary_service"], desiredCount=0)
        try:
            eventually(lambda: ecs.describe_services(cluster=manifest["ecs_cluster"], services=[manifest["canary_service"]])["services"][0]["runningCount"] == 0, timeout=60)
            return eventually(lambda: alarm(manifest, "telemetry_loss")["StateValue"] == "ALARM", timeout=210)
        finally:
            ecs.update_service(cluster=manifest["ecs_cluster"], service=manifest["canary_service"], desiredCount=1)
            eventually(lambda: ecs.describe_services(cluster=manifest["ecs_cluster"], services=[manifest["canary_service"]])["services"][0]["runningCount"] >= 1, timeout=60)

    check("telemetry-loss alarm", 2, telemetry_loss_alarm)

    def notification():
        token = "signalforge-route-" + uuid.uuid4().hex
        cloud("sns").publish(TopicArn=manifest["incident_topic_arn"], Message=token)
        return eventually(lambda: any(token in m.get("Body", "") for m in queue.receive_message(
            QueueUrl=manifest["incident_queue_url"], WaitTimeSeconds=1, MaxNumberOfMessages=10).get("Messages", [])), timeout=30)

    check("incident routing", 3, notification)
    check("layered health", 5, lambda: (
        requests.get(api_url + "/health/live", timeout=5).status_code == 200 and
        requests.get(api_url + "/health/ready", timeout=5).status_code == 200 and
        sample("JourneyGood", "canary") > 0
    ) or (_ for _ in ()).throw(AssertionError("health layers missing")))

    def synthetic_stall():
        ecs.update_service(cluster=manifest["ecs_cluster"], service=manifest["worker_service"], desiredCount=0)
        try:
            eventually(lambda: ecs.describe_services(cluster=manifest["ecs_cluster"], services=[manifest["worker_service"]])["services"][0]["runningCount"] == 0, timeout=60)
            assert requests.get(api_url + "/health/ready", timeout=5).status_code == 200
            assert eventually(lambda: sample("QueueBacklog", "canary", "Maximum") >= 1, timeout=90)
            assert eventually(lambda: sample("JourneyTotal", "canary") > sample("JourneyGood", "canary"), timeout=90)
            return "front door stayed ready while journey failed"
        finally:
            ecs.update_service(cluster=manifest["ecs_cluster"], service=manifest["worker_service"], desiredCount=1)

    check("synthetic hidden failure", 10, synthetic_stall)

    def dashboard():
        body = json.loads(cw.get_dashboard(DashboardName=manifest["dashboard"])["DashboardBody"])
        rendered = json.dumps(body)
        for name in ("RequestTotal", "RequestErrors", "RequestDurationMs", "CompletedJobs",
                     "JourneyGood", "JourneyTotal", "JourneyDurationMs", "QueueBacklog"):
            assert name in rendered, name
        assert "good/total" in rendered or "good / total" in rendered
        return len(body["widgets"])

    check("dashboard", 10, dashboard)
    check("declared topology", 5, lambda: all(t in types for t in (
        "aws_vpc", "aws_lb", "aws_ecs_service", "aws_sqs_queue", "aws_dynamodb_table",
        "aws_cloudwatch_log_group", "aws_cloudwatch_metric_alarm", "aws_cloudwatch_dashboard",
        "aws_sns_topic")) or (_ for _ in ()).throw(AssertionError("missing declared resource family")))
    check("live topology", 5, lambda: (
        len(ecs.describe_services(cluster=manifest["ecs_cluster"], services=[manifest["api_service"], manifest["worker_service"], manifest["canary_service"]])["services"]) == 3 and
        requests.get(api_url + "/health/ready", timeout=5).status_code == 200
    ) or (_ for _ in ()).throw(AssertionError("live topology not ready")))

    def lifecycle():
        dashboard_name = manifest["dashboard"]
        cw.delete_dashboards(DashboardNames=[dashboard_name])
        second = subprocess.run([str(SUBMISSION / "deploy.sh")], cwd=SUBMISSION, capture_output=True, text=True, timeout=720)
        assert second.returncode == 0, second.stderr[-1000:]
        cw.get_dashboard(DashboardName=dashboard_name)
        assert eventually(completed, timeout=60)
        destroy = subprocess.run([str(SUBMISSION / "destroy.sh")], cwd=SUBMISSION, capture_output=True, text=True, timeout=900)
        (LOG_DIR / "destroy.log").write_text((destroy.stdout + "\n" + destroy.stderr)[-1000000:])
        assert destroy.returncode == 0, destroy.stderr[-1000:]
        return "dashboard repaired and deployment destroyed"

    check("redeploy, repair, destroy", 10, lifecycle)
    save()


if __name__ == "__main__":
    main()
