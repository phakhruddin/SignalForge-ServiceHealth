resource "aws_cloudwatch_log_group" "service" {
  for_each          = toset(["api", "worker", "canary"])
  name              = "/ecs/${var.prefix}-${each.key}"
  retention_in_days = 7
}

resource "aws_sns_topic" "incidents" { name = "${var.prefix}-incidents" }
resource "aws_sqs_queue" "incidents" { name = "${var.prefix}-incident-events" }

resource "aws_sqs_queue_policy" "incidents" {
  queue_url = aws_sqs_queue.incidents.url
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Sid       = "AcceptIncidentTopic", Effect = "Allow", Principal = { Service = "sns.amazonaws.com" },
    Action    = "sqs:SendMessage", Resource = aws_sqs_queue.incidents.arn,
    Condition = { ArnEquals = { "aws:SourceArn" = aws_sns_topic.incidents.arn } }
  }] })
}

resource "aws_sns_topic_subscription" "incidents" {
  topic_arn  = aws_sns_topic.incidents.arn
  protocol   = "sqs"
  endpoint   = aws_sqs_queue.incidents.arn
  depends_on = [aws_sqs_queue_policy.incidents]
}

resource "aws_cloudwatch_metric_alarm" "api_errors" {
  alarm_name          = "${var.prefix}-api-errors"
  namespace           = var.metric_namespace
  metric_name         = "RequestErrors"
  dimensions          = local.dimensions_api
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.incidents.arn]
}

resource "aws_cloudwatch_metric_alarm" "api_latency" {
  alarm_name          = "${var.prefix}-api-latency"
  namespace           = var.metric_namespace
  metric_name         = "RequestDurationMs"
  dimensions          = local.dimensions_api
  statistic           = "Average"
  period              = 60
  evaluation_periods  = 1
  comparison_operator = "GreaterThanThreshold"
  threshold           = 1000
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.incidents.arn]
}

resource "aws_cloudwatch_metric_alarm" "backlog" {
  alarm_name          = "${var.prefix}-queue-backlog"
  namespace           = var.metric_namespace
  metric_name         = "QueueBacklog"
  dimensions          = local.dimensions_canary
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  treat_missing_data  = "missing"
  alarm_actions       = [aws_sns_topic.incidents.arn]
}

resource "aws_cloudwatch_metric_alarm" "journey_failure" {
  alarm_name          = "${var.prefix}-journey-failure"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  evaluation_periods  = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.incidents.arn]
  metric_query {
    id = "total"
    metric {
      namespace   = var.metric_namespace
      metric_name = "JourneyTotal"
      dimensions  = local.dimensions_canary
      period      = 60
      stat        = "Sum"
    }
  }
  metric_query {
    id = "good"
    metric {
      namespace   = var.metric_namespace
      metric_name = "JourneyGood"
      dimensions  = local.dimensions_canary
      period      = 60
      stat        = "Sum"
    }
  }
  metric_query {
    id          = "failed"
    expression  = "total-good"
    return_data = true
  }
}

resource "aws_cloudwatch_metric_alarm" "telemetry_loss" {
  alarm_name          = "${var.prefix}-canary-telemetry-loss"
  namespace           = var.metric_namespace
  metric_name         = "CanaryHeartbeat"
  dimensions          = local.dimensions_canary
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 2
  comparison_operator = "LessThanThreshold"
  threshold           = 1
  treat_missing_data  = "breaching"
  alarm_actions       = [aws_sns_topic.incidents.arn]
}

resource "aws_cloudwatch_dashboard" "service" {
  dashboard_name = "${var.prefix}-service-health"
  dashboard_body = jsonencode({ widgets = [
    { type = "text", x = 0, y = 0, width = 24, height = 2,
    properties = { markdown = "# SignalForge service health\nALB readiness proves only the front door. JourneyGood / JourneyTotal proves completed customer work." } },
    { type = "metric", x = 0, y = 2, width = 12, height = 6,
      properties = { title = "API traffic and errors", region = var.region, stat = "Sum", period = 60,
        metrics = [[var.metric_namespace, "RequestTotal", "Deployment", var.prefix, "Service", "api"],
    [var.metric_namespace, "RequestErrors", "Deployment", var.prefix, "Service", "api"]] } },
    { type = "metric", x = 12, y = 2, width = 12, height = 6,
      properties = { title = "API duration", region = var.region, stat = "Average", period = 60,
    metrics = [[var.metric_namespace, "RequestDurationMs", "Deployment", var.prefix, "Service", "api"]] } },
    { type = "metric", x = 0, y = 8, width = 12, height = 6,
      properties = { title = "Worker completions and errors", region = var.region, stat = "Sum", period = 60,
        metrics = [[var.metric_namespace, "CompletedJobs", "Deployment", var.prefix, "Service", "worker"],
    [var.metric_namespace, "ProcessingErrors", "Deployment", var.prefix, "Service", "worker"]] } },
    { type = "metric", x = 12, y = 8, width = 12, height = 6,
      properties = { title = "Journey good and total", region = var.region, stat = "Sum", period = 60,
        metrics = [[var.metric_namespace, "JourneyGood", "Deployment", var.prefix, "Service", "canary"],
          [var.metric_namespace, "JourneyTotal", "Deployment", var.prefix, "Service", "canary"],
    [var.metric_namespace, "JourneyDurationMs", "Deployment", var.prefix, "Service", "canary", { stat = "Average" }]] } },
    { type = "metric", x = 0, y = 14, width = 12, height = 6,
      properties = { title = "Queue backlog", region = var.region, stat = "Maximum", period = 60,
    metrics = [[var.metric_namespace, "QueueBacklog", "Deployment", var.prefix, "Service", "canary"]] } },
    { type = "metric", x = 12, y = 14, width = 12, height = 6,
      properties = { title = "Journey SLI: good / total", region = var.region, period = 60,
        metrics = [
          [var.metric_namespace, "JourneyGood", "Deployment", var.prefix, "Service", "canary", { id = "good", stat = "Sum", visible = false }],
          [var.metric_namespace, "JourneyTotal", "Deployment", var.prefix, "Service", "canary", { id = "total", stat = "Sum", visible = false }],
          [{ expression = "100*good/total", label = "Journey success %", id = "sli" }]
    ] } }
  ] })
}
