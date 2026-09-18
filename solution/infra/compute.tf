resource "aws_lb" "api" {
  name               = "${var.prefix}-api"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
}

resource "aws_lb_target_group" "api" {
  name        = "${var.prefix}-api"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"
  health_check {
    enabled             = true
    path                = "/health/ready"
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 5
    timeout             = 3
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_ecs_cluster" "main" { name = "${var.prefix}-cluster" }

locals {
  base_env = [
    { name = "RESOURCE_PREFIX", value = var.prefix },
    { name = "AWS_REGION", value = var.region },
    { name = "AWS_DEFAULT_REGION", value = var.region },
    { name = "AWS_ENDPOINT_URL", value = var.endpoint },
    { name = "AWS_ACCESS_KEY_ID", value = var.aws_access_key_id },
    { name = "AWS_SECRET_ACCESS_KEY", value = var.aws_secret_access_key },
    { name = "METRIC_NAMESPACE", value = var.metric_namespace },
  ]
  job_env = [
    { name = "QUEUE_URL", value = aws_sqs_queue.jobs.url },
    { name = "RESULT_TABLE", value = aws_dynamodb_table.results.name },
  ]
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.prefix}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.api.arn
  container_definitions = jsonencode([{
    name         = "api", image = var.api_image, essential = true,
    portMappings = [{ containerPort = 8080, hostPort = 8080, protocol = "tcp" }],
    environment  = concat(local.base_env, local.job_env, [{ name = "LOG_GROUP", value = aws_cloudwatch_log_group.service["api"].name }]),
    logConfiguration = { logDriver = "awslogs", options = {
      "awslogs-group"  = aws_cloudwatch_log_group.service["api"].name,
      "awslogs-region" = var.region, "awslogs-stream-prefix" = "api"
    } }
  }])
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.prefix}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.worker.arn
  container_definitions = jsonencode([{
    name        = "worker", image = var.worker_image, essential = true,
    environment = concat(local.base_env, local.job_env, [{ name = "LOG_GROUP", value = aws_cloudwatch_log_group.service["worker"].name }]),
    logConfiguration = { logDriver = "awslogs", options = {
      "awslogs-group"  = aws_cloudwatch_log_group.service["worker"].name,
      "awslogs-region" = var.region, "awslogs-stream-prefix" = "worker"
    } }
  }])
}

resource "aws_ecs_task_definition" "canary" {
  family                   = "${var.prefix}-canary"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.canary.arn
  container_definitions = jsonencode([{
    name = "canary", image = var.canary_image, essential = true,
    environment = concat(local.base_env, [
      { name = "PUBLIC_API_URL", value = local.api_url },
      { name = "QUEUE_URL", value = aws_sqs_queue.jobs.url },
      { name = "LOG_GROUP", value = aws_cloudwatch_log_group.service["canary"].name },
    ]),
    logConfiguration = { logDriver = "awslogs", options = {
      "awslogs-group"  = aws_cloudwatch_log_group.service["canary"].name,
      "awslogs-region" = var.region, "awslogs-stream-prefix" = "canary"
    } }
  }])
}

resource "aws_ecs_service" "api" {
  name                              = "${var.prefix}-api"
  cluster                           = aws_ecs_cluster.main.id
  task_definition                   = aws_ecs_task_definition.api.arn
  desired_count                     = 2
  launch_type                       = "FARGATE"
  health_check_grace_period_seconds = 60
  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.api.id]
    assign_public_ip = false
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8080
  }
  depends_on = [aws_lb_listener.http]
}

resource "aws_ecs_service" "worker" {
  name            = "${var.prefix}-worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.background.id]
    assign_public_ip = false
  }
}

resource "aws_ecs_service" "canary" {
  name            = "${var.prefix}-canary"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.canary.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.background.id]
    assign_public_ip = false
  }
  depends_on = [aws_ecs_service.api, aws_ecs_service.worker]
}
