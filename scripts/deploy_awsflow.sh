#!/usr/bin/env bash
# Run explicitly in an authenticated AWS CloudShell session; this creates resources.
set -euo pipefail

TASK_REGION="${AWSFLOW_REGION:-us-east-1}"
TASK_STACK="${AWSFLOW_STACK:-awsflow-demo}"
TASK_DATABASE="${AWSFLOW_DATABASE:-awsflow_demo}"
TASK_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
TASK_ARTIFACT_BUCKET="awsflow-artifacts-${TASK_ACCOUNT}-${TASK_REGION}"

if [[ "$TASK_REGION" != "us-east-1" ]]; then
  echo "This bounded demo script currently supports us-east-1 only."
  exit 1
fi

python3 infra/build_awsflow.py
TASK_HASH="$(sha256sum data/awsflow-worker.zip | cut -d ' ' -f 1)"
TASK_ARTIFACT_KEY="lambda/${TASK_HASH}.zip"

if ! aws s3api head-bucket --bucket "$TASK_ARTIFACT_BUCKET" --region "$TASK_REGION" 2>/dev/null; then
  aws s3api create-bucket --bucket "$TASK_ARTIFACT_BUCKET" --region "$TASK_REGION"
fi
aws s3api put-public-access-block --bucket "$TASK_ARTIFACT_BUCKET" --public-access-block-configuration 'BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true' --region "$TASK_REGION"
aws s3api put-bucket-encryption --bucket "$TASK_ARTIFACT_BUCKET" --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}' --region "$TASK_REGION"
aws s3 cp data/awsflow-worker.zip "s3://${TASK_ARTIFACT_BUCKET}/${TASK_ARTIFACT_KEY}" --sse AES256 --region "$TASK_REGION"

aws cloudformation validate-template --template-body file://infra/awsflow/template.json --region "$TASK_REGION"
aws cloudformation deploy --template-file infra/awsflow/template.json --stack-name "$TASK_STACK" --capabilities CAPABILITY_IAM --parameter-overrides "ArtifactBucket=${TASK_ARTIFACT_BUCKET}" "ArtifactKey=${TASK_ARTIFACT_KEY}" "DatabaseName=${TASK_DATABASE}" --region "$TASK_REGION" --no-fail-on-empty-changeset
aws cloudformation describe-stacks --stack-name "$TASK_STACK" --query 'Stacks[0].Outputs' --region "$TASK_REGION"

echo "Stack deployed. Read docs/awsflow-deployment.md before uploading input or running Athena queries."
