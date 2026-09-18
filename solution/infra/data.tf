resource "aws_sqs_queue" "jobs" {
  name                       = "${var.prefix}-jobs"
  visibility_timeout_seconds = 30
  message_retention_seconds  = 3600
}

resource "aws_dynamodb_table" "results" {
  name         = "${var.prefix}-results"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "job_id"
  attribute {
    name = "job_id"
    type = "S"
  }
}
