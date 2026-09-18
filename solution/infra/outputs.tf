output "manifest" {
  value = {
    resource_prefix    = var.prefix
    api_url            = local.api_url
    ecs_cluster        = aws_ecs_cluster.main.name
    api_service        = aws_ecs_service.api.name
    worker_service     = aws_ecs_service.worker.name
    canary_service     = aws_ecs_service.canary.name
    job_queue_url      = aws_sqs_queue.jobs.url
    result_table       = aws_dynamodb_table.results.name
    dashboard          = aws_cloudwatch_dashboard.service.dashboard_name
    incident_topic_arn = aws_sns_topic.incidents.arn
    incident_queue_url = aws_sqs_queue.incidents.url
    log_groups         = { for name, group in aws_cloudwatch_log_group.service : name => group.name }
    alarms = {
      api_errors      = aws_cloudwatch_metric_alarm.api_errors.alarm_name
      api_latency     = aws_cloudwatch_metric_alarm.api_latency.alarm_name
      backlog         = aws_cloudwatch_metric_alarm.backlog.alarm_name
      journey_failure = aws_cloudwatch_metric_alarm.journey_failure.alarm_name
      telemetry_loss  = aws_cloudwatch_metric_alarm.telemetry_loss.alarm_name
    }
  }
}
