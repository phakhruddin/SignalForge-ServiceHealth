# Observability contract

The supplied images publish to the `metric_namespace` from runtime config.
Every sample uses dimensions `Deployment=<resource_prefix>` and
`Service=api|worker|canary`. Do not modify those values. Create monitoring
resources that use these real series; a dashboard or alarm pointed at a
different namespace or dimensions does not observe the service.

| Service | Emitted metrics | Unit and interpretation |
|---|---|---|
| API | `RequestTotal`, `RequestErrors`, `AcceptedJobs` | Count per relevant request or accepted job. Health checks are excluded from request metrics. |
| API | `RequestDurationMs` | Milliseconds for each non-health HTTP request. |
| Worker | `WorkerHeartbeat`, `CompletedJobs`, `ProcessingErrors` | Count; heartbeat is sent on each polling pass. |
| Worker | `ProcessingDurationMs` | Milliseconds per completed job. |
| Canary | `JourneyTotal`, `JourneyGood`, `CanaryHeartbeat` | Count; `JourneyGood` publishes 1 for success and 0 for failure. |
| Canary | `QueueBacklog` | Count of visible SQS messages observed through `GetQueueAttributes`. |
| Canary | `JourneyDurationMs` | Milliseconds from submission until completion or timeout. |

The primary service-level indicator is completed journeys divided by total
journeys over the same window, using the `Sum` statistic of `JourneyGood` and
`JourneyTotal`. Its service-level goal is at least 99% success. The API
acceptance indicator is `1 - RequestErrors/RequestTotal`, also using `Sum`,
with goal at least 99.5%. Never use `AcceptedJobs` as a substitute for
completed customer journeys. It is valid to express ratios as dashboard
metric math; the model need not publish derived metrics.

Create one CloudWatch dashboard whose widgets make the following inspectable:
API request count, error count and duration; worker completion and processing
errors; canary journey good/total and duration; and the journey SLI ratio.
Use the actual runtime namespace and dimensions. Include a text widget that
explains why ALB health and customer-journey health can disagree.

Create CloudWatch **metric alarms** for these conditions, with task-owned
names and alarm actions to the incident SNS topic:

1. API errors: `RequestErrors` Sum is at least 1 in a 60-second period.
2. API latency: `RequestDurationMs` Average exceeds 1000 milliseconds in a
   60-second period.
3. Queue backlog: canary `QueueBacklog` Maximum is at least 1 in a 60-second
   period. The canary's sample must come from the live job queue attribute.
4. Journey failure: a canary `JourneyTotal` versus `JourneyGood` metric-math
   expression detects any completed failed journey in a 60-second period.
5. Telemetry loss: absent `CanaryHeartbeat` data must be treated as breaching,
   not OK, after the chosen evaluation window.

All alarms must name their metric dimensions and use at least one evaluation
period. Alarm action ARN must refer to a Terraform-managed SNS topic. Route
that topic to a Terraform-managed SQS incident queue so a verifier can
inspect notification messages. Do not manually set alarm states as the
monitoring implementation. If Floci cannot demonstrate an automatic state
transition for a specific alarm, the verifier may check its metric source,
threshold, missing-data policy, and live metric samples separately; it must
not report a transition that did not happen.

Create distinct CloudWatch log groups for API, worker, and canary, with at
least seven days of retention. The supplied programs emit one-line JSON with
`timestamp`, `service`, `deployment`, `level`, and `event`. API request logs
also carry `request_id`, `trace_id`, `status`, and `duration_ms`. API
`job_accepted` and worker `job_completed` records carry the same `job_id`
and `trace_id`; their `span_id` and `parent_span_id` fields link the worker
record to the API record. The canary logs its `trace_id`, `job_id`, and
`good` result. Pass each group name as `LOG_GROUP` to its program and grant
its task role `logs:CreateLogStream` and `logs:PutLogEvents` for that group.
The programs publish their records directly because this local ECS runtime
records container stdout in Docker but does not forward it through the
configured `awslogs` log driver. Logs must be retrievable through CloudWatch
Logs, not merely stdout in a Docker container. Do not log credentials or a submitted `secret`
field. The span fields are structured correlation records, not native X-Ray
spans.
