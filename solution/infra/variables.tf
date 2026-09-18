variable "prefix" { type = string }
variable "region" { type = string }
variable "endpoint" { type = string }
variable "metric_namespace" { type = string }
variable "api_image" { type = string }
variable "worker_image" { type = string }
variable "canary_image" { type = string }
variable "aws_access_key_id" {
  type      = string
  sensitive = true
}
variable "aws_secret_access_key" {
  type      = string
  sensitive = true
}
