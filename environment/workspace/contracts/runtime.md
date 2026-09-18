# SignalForge runtime contract

`/workspace/config/config.json` is generated separately for every rollout. It
contains `resource_prefix`, `region`, `aws_endpoint_url`, `api_image`,
`worker_image`, `canary_image`, corresponding `_image_id` values, and
`metric_namespace`. Read it when each lifecycle script runs. The workspace
already sets test AWS credentials. All cloud calls go to `aws_endpoint_url`.

The three images are already built and approved. Use the exact image names in
the config; do not rebuild them. Each image starts its intended process with
its default command and is built for the local Docker host architecture.

All three processes accept `RESOURCE_PREFIX`, `AWS_REGION`,
`AWS_ENDPOINT_URL`, `METRIC_NAMESPACE`, and `LOG_GROUP`. API and worker also require
`QUEUE_URL` and `RESULT_TABLE`. Canary requires `PUBLIC_API_URL` and `QUEUE_URL`, the ALB
connect URL, and accepts `CANARY_INTERVAL_SECONDS` (default 15). In the local
cloud the ECS task role must permit the AWS actions, but the AWS-compatible
credential values supplied to the workspace must also be passed to tasks as
`AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` for SDK signing.

The API listens on port 8080:

| Request | Result |
|---|---|
| `GET /health/live` | HTTP 200 when the process is running. |
| `GET /health/ready` | HTTP 200 only when SQS and DynamoDB dependencies can be described; HTTP 503 otherwise. This is the ALB target-group path. |
| `POST /v1/jobs` with JSON `{"value":"text"}` | HTTP 202 with `job_id`, `trace_id`, and `status: accepted`; sends one SQS message. |
| `GET /v1/jobs/{job_id}` | HTTP 202 while pending, or HTTP 200 with `status: completed` and the stored value. |

For deterministic diagnostic requests, `X-SignalForge-Mode: fail` on a job
POST returns 503 without enqueuing. `X-SignalForge-Mode: slow` delays a valid
POST by about 1.5 seconds. These headers are documented fault stimuli, not
authorization controls. `X-Trace-Id` may be supplied by the caller; otherwise
the API generates one. A client may include a field named `secret`, but that
field must not appear in application logs.

The worker long-polls SQS, stores results in DynamoDB, and deletes each
successfully processed message. Its ECS desired count is one or more. A
stalled-worker experiment may temporarily set that count to zero; a normal
redeploy must restore the declared count. The canary repeatedly submits a
fresh job via the public ALB and polls for completion. Its ECS desired count
is one. It emits a failed journey if the result does not complete in ten
seconds, even if the initial POST returned 202.

The job message includes `job_id`, `trace_id`, and `value`. The result table
uses string partition key `job_id` and stores `value`, `trace_id`, and
`completed_at`. These names are part of the application contract.
