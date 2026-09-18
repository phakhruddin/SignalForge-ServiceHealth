FROM --platform=linux/amd64 mirror.gcr.io/library/python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7
ARG TERRAFORM_VERSION=1.15.8
ARG AWS_PROVIDER_VERSION=6.51.0
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION=us-east-1 \
    AWS_ENDPOINT_URL=http://aws:4566 \
    TF_CLI_CONFIG_FILE=/etc/terraformrc.offline
RUN apt-get update && apt-get install -y --no-install-recommends \
      bash ca-certificates curl unzip jq procps && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir boto3 requests jsonschema \
 && curl -fsSLo /tmp/terraform.zip \
      "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip" \
 && unzip -q /tmp/terraform.zip -d /usr/local/bin && rm /tmp/terraform.zip
RUN mkdir -p /opt/terraform-plugin-cache /tmp/provider-seed \
 && printf 'terraform {\n  required_providers {\n    aws = { source = "hashicorp/aws", version = "=%s" }\n  }\n}\n' "$AWS_PROVIDER_VERSION" > /tmp/provider-seed/main.tf \
 && TF_PLUGIN_CACHE_DIR=/opt/terraform-plugin-cache TF_CLI_CONFIG_FILE=/dev/null terraform -chdir=/tmp/provider-seed init -backend=false -input=false \
 && rm -rf /tmp/provider-seed \
 && printf 'disable_checkpoint = true\nprovider_installation {\n  filesystem_mirror {\n    path = "/opt/terraform-plugin-cache"\n    include = ["registry.terraform.io/hashicorp/aws"]\n  }\n  direct {\n    exclude = ["registry.terraform.io/hashicorp/aws"]\n  }\n}\n' > /etc/terraformrc.offline
COPY tests/ /tests/
WORKDIR /tests
