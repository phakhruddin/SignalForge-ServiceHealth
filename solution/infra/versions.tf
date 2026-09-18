terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "= 6.51.0" }
  }
}

provider "aws" {
  access_key                  = var.aws_access_key_id
  secret_key                  = var.aws_secret_access_key
  region                      = var.region
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  skip_region_validation      = true
  s3_use_path_style           = true

  default_tags { tags = { Project = "signalforge-servicehealth", Deployment = var.prefix, ManagedBy = "terraform" } }

  endpoints {
    cloudwatch             = var.endpoint
    dynamodb               = var.endpoint
    ec2                    = var.endpoint
    ecs                    = var.endpoint
    elasticloadbalancingv2 = var.endpoint
    iam                    = var.endpoint
    logs                   = var.endpoint
    sns                    = var.endpoint
    sqs                    = var.endpoint
  }
}
