locals {
  ecs_trust = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "ecs-tasks.amazonaws.com" }
  }] })
}

resource "aws_iam_role" "execution" {
  name               = "${var.prefix}-execution"
  assume_role_policy = local.ecs_trust
}
resource "aws_iam_role" "api" {
  name               = "${var.prefix}-api"
  assume_role_policy = local.ecs_trust
}
resource "aws_iam_role" "worker" {
  name               = "${var.prefix}-worker"
  assume_role_policy = local.ecs_trust
}
resource "aws_iam_role" "canary" {
  name               = "${var.prefix}-canary"
  assume_role_policy = local.ecs_trust
}

resource "aws_iam_role_policy" "execution" {
  role = aws_iam_role.execution.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect   = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"],
    Resource = [for group in aws_cloudwatch_log_group.service : "${group.arn}:*"]
  }] })
}

resource "aws_iam_role_policy" "api" {
  role = aws_iam_role.api.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["sqs:SendMessage", "sqs:GetQueueAttributes"], Resource = aws_sqs_queue.jobs.arn },
    { Effect = "Allow", Action = ["dynamodb:DescribeTable", "dynamodb:GetItem"], Resource = aws_dynamodb_table.results.arn },
    { Effect = "Allow", Action = ["cloudwatch:PutMetricData"], Resource = "*" },
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.service["api"].arn}:*" }
  ] })
}
resource "aws_iam_role_policy" "worker" {
  role = aws_iam_role.worker.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"], Resource = aws_sqs_queue.jobs.arn },
    { Effect = "Allow", Action = ["dynamodb:PutItem"], Resource = aws_dynamodb_table.results.arn },
    { Effect = "Allow", Action = ["cloudwatch:PutMetricData"], Resource = "*" },
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.service["worker"].arn}:*" }
  ] })
}
resource "aws_iam_role_policy" "canary" {
  role = aws_iam_role.canary.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["cloudwatch:PutMetricData"], Resource = "*" },
    { Effect = "Allow", Action = ["sqs:GetQueueAttributes"], Resource = aws_sqs_queue.jobs.arn },
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.service["canary"].arn}:*" }
  ] })
}
