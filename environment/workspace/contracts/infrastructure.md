# SignalForge infrastructure contract

The deployment owns a VPC with two public and two private subnets in two
availability zones. A public ALB listens on HTTP port 80. Only the ALB is
public; ECS tasks have no public IP. The ALB security group accepts the
public HTTP traffic, and the API security group accepts port 8080 from that
ALB group. Worker and canary do not require inbound listeners. The local
Floci endpoint is reachable from all tasks through its Compose network;
network security groups are checked as declared configuration because Floci
may not enforce every rule.

Run the API as a Fargate-compatible ECS service with at least two desired
replicas. Run worker and canary as separate Fargate-compatible ECS services.
The API target group uses `/health/ready`, not `/health/live`. The worker must
have permission to receive/delete from the task queue and write the result
table. The API must be able to send to that queue and read that table. All
three services need permission to publish custom CloudWatch metrics and
write their own CloudWatch logs; the canary may read the job queue's
approximate-depth attribute but must not receive or delete messages or read
the result table directly.

Create an SQS standard queue for jobs and a DynamoDB table for results. Keep
the table and queue stable across repeat deploys. All resources must be
managed by Terraform or OpenTofu. The deployment may create supporting IAM,
route, key, or endpoint resources necessary for this topology. No public API
authentication is required in this scenario; the fixed workload tests service
health, not identity.

The monitoring resource requirements are in `observability.md`. Monitoring
resources are first-class deployment resources, not optional decorations.
If a task-owned dashboard or alarm is deleted after a successful deployment,
the next `deploy.sh` invocation must restore it. `destroy.sh` removes task-owned
resources only. It must never delete the baseline resources that existed
before the attempt.
