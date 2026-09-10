#!/usr/bin/env bash
# DQC PoC — CloudFormation deployment script
#
# Deploys DQC backend on AWS in two stages:
#   Stage 1: Infrastructure (ECS, ECR, ALB, S3, DynamoDB, IAM) — dqc-infrastructure.yaml
#   Stage 2: Serverless (Lambda, API Gateway, Layers) — dqc-serverless.yaml
#
# Resolves defects:
#   #4  — Configure AWS backend with application
#   #5  — Create API to call Nova Micro via .env
#   #6  — Create main S3 bucket
#   #7  — Lambda to find implicated fields (LangChain)
#   #8  — Create CloudFormation scripts (this script)
#   #9  — Lambda to generate SQL with retry + LLM-as-judge
#   #10 — DynamoDB to store DQCs by project
#
# Usage:
#   ./deploy.sh [--region eu-west-1] [--stack-name dqc-poc] [--destroy] [--confirm]
#
# Prerequisites:
#   - AWS CLI configured (aws configure or SSO)
#   - Python 3.11+ (for Lambda layer builds)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_NAME="${STACK_NAME:-dqc-poc}"
AWS_REGION="${AWS_REGION:-eu-west-1}"
CONFIRM="${CONFIRM:-false}"
DESTROY="${DESTROY:-false}"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --region)
      AWS_REGION="$2"
      shift 2
      ;;
    --stack-name)
      STACK_NAME="$2"
      shift 2
      ;;
    --destroy)
      DESTROY=true
      shift
      ;;
    --confirm)
      CONFIRM=true
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [--region eu-west-1] [--stack-name dqc-poc] [--destroy] [--confirm]"
      echo ""
      echo "Options:"
      echo "  --region       AWS region (default: eu-west-1)"
      echo "  --stack-name   CloudFormation stack name (default: dqc-poc)"
      echo "  --destroy      Destroy the stack instead of deploying"
      echo "  --confirm      Skip confirmation prompt"
      echo "  -h, --help     Show this help"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)

# ── Verify AWS credentials ──────────────────────────────────────────────
echo "=== DQC PoC — CloudFormation Deployment ==="
echo ""
echo "==> Verifying AWS credentials..."

if ! aws sts get-caller-identity --query 'Arn' --output text > /dev/null 2>&1; then
  echo "ERROR: AWS credentials not configured. Run 'aws configure' or 'aws configure sso'."
  exit 1
fi

echo "    Account: ${ACCOUNT_ID}"
echo "    Region:  ${AWS_REGION}"
echo "    Stack:   ${STACK_NAME}"
echo ""

# ── VPC detection ──────────────────────────────────────────────────────
echo "==> Detecting VPC and subnets..."

VPC_ID=$(aws ec2 describe-vpcs \
  --region "${AWS_REGION}" \
  --filters "Name=isDefault,Values=true" \
  --query 'Vpcs[0].VpcId' --output text 2>/dev/null || echo "")

if [[ "${VPC_ID}" == "None" ]] || [[ -z "${VPC_ID}" ]]; then
  echo "    No default VPC found. Creating default VPC..."
  VPC_ID=$(aws ec2 create-default-vpc --query 'Vpc.VpcId' --output text --region "${AWS_REGION}" 2>/dev/null || echo "")
  if [[ "${VPC_ID}" == "None" ]] || [[ -z "${VPC_ID}" ]]; then
    echo "    ERROR: Could not create default VPC. Please provide VPC and subnet IDs manually."
    echo "    Use: --stack-name ${STACK_NAME} --vpc-id vpc-xxx --subnet-ids subnet-xxx,subnet-yyy"
    exit 1
  fi
  echo "    Created VPC: ${VPC_ID}"
fi

SUBNET_IDS=$(aws ec2 describe-subnets \
  --region "${AWS_REGION}" \
  --filters "Name=vpc-id,Values=${VPC_ID}" \
  --query 'Subnets[*].SubnetId' --output text)

SUBNET_CSV=$(echo "${SUBNET_IDS}" | tr '\t' ',')

if [[ -z "${SUBNET_CSV}" ]] || [[ "${SUBNET_CSV}" == "None" ]]; then
  echo "ERROR: No subnets found in VPC ${VPC_ID}"
  exit 1
fi

echo "    VPC: ${VPC_ID}"
echo "    Subnets: ${SUBNET_CSV}"
echo ""

# ── Deploy / Destroy ───────────────────────────────────────────────────
if [[ "${DESTROY}" == "true" ]]; then
  echo "==> Destroying stack: ${STACK_NAME}"
  echo ""

  if [[ "${CONFIRM}" != "true" ]]; then
    read -p "Are you sure you want to destroy the stack? This will delete all resources. [y/N] " confirm
    if [[ "${confirm}" != [yY] ]]; then
      echo "Aborted."
      exit 0
    fi
  fi

  # Destroy serverless first (depends on infrastructure)
  echo "    [1/2] Destroying serverless stack..."
  aws cloudformation delete-stack \
    --stack-name "${STACK_NAME}-serverless" \
    --region "${AWS_REGION}" || true

  aws cloudformation wait stack-delete-complete \
    --stack-name "${STACK_NAME}-serverless" \
    --region "${AWS_REGION}" 2>/dev/null || true

  echo "    [2/2] Destroying infrastructure stack..."
  aws cloudformation delete-stack \
    --stack-name "${STACK_NAME}-infrastructure" \
    --region "${AWS_REGION}"

  aws cloudformation wait stack-delete-complete \
    --stack-name "${STACK_NAME}-infrastructure" \
    --region "${AWS_REGION}"

  # Also delete main stack if it exists
  aws cloudformation delete-stack \
    --stack-name "${STACK_NAME}" \
    --region "${AWS_REGION}" 2>/dev/null || true

  echo ""
  echo "✓ Stack destroyed."
  exit 0
fi

# ── Stage 0: Build Lambda layer ────────────────────────────────────────
echo "==> Building Lambda layer (LangChain + Bedrock)..."
cd "${SCRIPT_DIR}/lambda-layers/langchain-layer"
python3 -m venv /tmp/langchain-layer-venv
source /tmp/langchain-layer-venv/bin/activate
pip install -r requirements.txt --target ./python/ --quiet 2>/dev/null
deactivate
rm -rf /tmp/langchain-layer-venv

if [[ -f layer.zip ]]; then
  rm layer.zip
fi
zip -r layer.zip python/ > /dev/null 2>&1
echo "    Layer ZIP created: layer.zip"
echo ""

# ── Stage 0b: Package Lambda functions ─────────────────────────────────
for func_dir in find-fields sql-generator bcbs-classifier; do
  echo "==> Packaging Lambda: ${func_dir}..."
  cd "${SCRIPT_DIR}/lambda-functions/${func_dir}"

  if [[ -f requirements.txt ]]; then
    python3 -m venv /tmp/lambda-venv
    source /tmp/lambda-venv/bin/activate
    pip install -r requirements.txt --target ./package/ --quiet 2>/dev/null
    deactivate
    rm -rf /tmp/lambda-venv

    if [[ -f package.zip ]]; then
      rm package.zip
    fi
    zip -r package.zip . -x "*.pyc" -x "__pycache__/*" > /dev/null 2>&1
  fi

  echo "    ${func_dir} packaged."
done

cd "${SCRIPT_DIR}"
echo ""

# ── Stage 1: Deploy Infrastructure ─────────────────────────────────────
echo "=== Stage 1: Deploying Infrastructure ==="
echo ""

DEPLOY_INFRA_CMD="aws cloudformation deploy \
  --stack-name '${STACK_NAME}-infrastructure' \
  --template-file '${SCRIPT_DIR}/dqc-infrastructure.yaml' \
  --region '${AWS_REGION}' \
  --parameter-overrides \
    ProjectName=${STACK_NAME} \
    AWSRegion=${AWS_REGION} \
    VpcId=${VPC_ID} \
    SubnetIds=${SUBNET_CSV} \
    BedrockModelId=eu.amazon.nova-micro-v1:0 \
    CPUC_units=1024 \
    MemoryMiB=4096 \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset \
  --tags 'Project=dqc-poc' 'ManagedBy=cloudformation' 'Stage=infrastructure'"

echo "${DEPLOY_INFRA_CMD}"
echo ""
eval "${DEPLOY_INFRA_CMD}"

echo ""

# ── Stage 2: Deploy Serverless ─────────────────────────────────────────
echo "=== Stage 2: Deploying Serverless (Lambda + API Gateway) ==="
echo ""

DEPLOY_SERVERLESS_CMD="aws cloudformation deploy \
  --stack-name '${STACK_NAME}-serverless' \
  --template-file '${SCRIPT_DIR}/dqc-serverless.yaml' \
  --region '${AWS_REGION}' \
  --parameter-overrides \
    ProjectName=${STACK_NAME} \
    AWSRegion=${AWS_REGION} \
    BedrockModelId=eu.amazon.nova-micro-v1:0 \
    JudgeBedrockModelId=eu.amazon.nova-pro-v1:0 \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset \
  --tags 'Project=dqc-poc' 'ManagedBy=cloudformation' 'Stage=serverless'"

echo "${DEPLOY_SERVERLESS_CMD}"
echo ""
eval "${DEPLOY_SERVERLESS_CMD}"

echo ""

# ── Upload data to S3 ─────────────────────────────────────────────────
echo "=== Uploading Data to S3 ==="
echo ""

S3_BUCKET="${STACK_NAME}-data-${ACCOUNT_ID}"
echo "    S3 bucket: ${S3_BUCKET}"

# Create bucket
aws s3 mb "s3://${S3_BUCKET}" --region "${AWS_REGION}" 2>/dev/null || true

# Upload prompts
echo "    Uploading prompts..."
for prompt_file in "${SCRIPT_DIR}/data/prompts/"*.md; do
  if [[ -f "${prompt_file}" ]]; then
    fname=$(basename "${prompt_file}" .md)
    aws s3 cp "${prompt_file}" "s3://${S3_BUCKET}/prompts/${fname}.md" --region "${AWS_REGION}" --quiet
  fi
done

# Upload rules
echo "    Uploading rules..."
for rule_file in "${SCRIPT_DIR}/data/rules/"*.txt; do
  if [[ -f "${rule_file}" ]]; then
    fname=$(basename "${rule_file}")
    aws s3 cp "${rule_file}" "s3://${S3_BUCKET}/rules/${fname}" --region "${AWS_REGION}" --quiet
  fi
done

# Upload anonymized data
echo "    Uploading anonymized data..."
for data_file in "${SCRIPT_DIR}/data/anonymized/"*.json; do
  if [[ -f "${data_file}" ]]; then
    fname=$(basename "${data_file}")
    aws s3 cp "${data_file}" "s3://${S3_BUCKET}/anonymized/${fname}" --region "${AWS_REGION}" --quiet
  fi
done

echo ""

# ── Print outputs ──────────────────────────────────────────────────────
echo "============================================================"
echo "  DQC PoC — CloudFormation deployment complete!"
echo "============================================================"
echo ""

echo "  Resources created:"
echo "  ┌─────────────────────────────────────────────────────────┐"
echo "  │ Infrastructure (Stage 1):                               │"
echo "  │   ECS Cluster/Service: ${STACK_NAME}                      │"
echo "  │   ECR Repos: ${STACK_NAME}-api, ${STACK_NAME}-dqc           │"
echo "  │   ALB: http://<alb-dns>                                 │"
echo "  │   S3 Bucket: ${STACK_NAME}-data-${ACCOUNT_ID}              │"
echo "  │   DynamoDB Table: ${STACK_NAME}-dqc-store                │"
echo "  │   IAM Roles: ${STACK_NAME}-ecs-exec, ${STACK_NAME}-ecs-task │"
echo "  └─────────────────────────────────────────────────────────┘"
echo ""
echo "  Serverless (Stage 2):"
echo "  ┌─────────────────────────────────────────────────────────┐"
echo "  │   Lambda: ${STACK_NAME}-find-fields          (Issue #7)  │"
echo "  │   Lambda: ${STACK_NAME}-sql-generator        (Issue #9)  │"
echo "  │   Lambda: ${STACK_NAME}-bcbs-classifier      (Issue #2)  │"
echo "  │   API Gateway: ${STACK_NAME}-dqc-api         (Issues #4,#5)│"
echo "  │   Lambda Layer: ${STACK_NAME}-langchain-layer              │"
echo "  └─────────────────────────────────────────────────────────┘"
echo ""

# Get API Gateway URL
API_URL=$(aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}-serverless" \
  --region "${AWS_REGION}" \
  --query "Stacks[0].Outputs[?OutputKey=='DqcApiUrl'].OutputValue" \
  --output text 2>/dev/null || echo "")

echo "  .env.example (copy to .env.local):"
echo ""
cat << ENV_EOF

# DQC PoC — CloudFormation outputs (generated for ${STACK_NAME})
# Copy this file to .env.local and update values

# ── API Gateway (Issues #4, #5) ──
DQC_API_URL=${API_URL}
DQC_API_FIELDS=\${DQC_API_URL}/fields
DQC_API_GENERATE=\${DQC_API_URL}/generate
DQC_API_JUDGE=\${DQC_API_URL}/judge
DQC_API_BCBS=\${DQC_API_URL}/bcbs
DQC_API_CHECKS=\${DQC_API_URL}/checks
DQC_API_HEALTH=\${DQC_API_URL}/health

# ── S3 (Issue #6) ──
DQC_S3_BUCKET=${STACK_NAME}-data-${ACCOUNT_ID}
DQC_S3_REGION=${AWS_REGION}

# ── DynamoDB (Issue #10) ──
DQC_DYNAMODB_TABLE=${STACK_NAME}-dqc-store
DQC_DYNAMODB_REGION=${AWS_REGION}

# ── Bedrock ──
BEDROCK_MODEL_ID=eu.amazon.nova-micro-v1:0
BEDROCK_JUDGE_MODEL_ID=eu.amazon.nova-pro-v1:0
BEDROCK_REGION=${AWS_REGION}

# ── Lambda Functions ──
LAMBDA_FIND_FIELDS=${STACK_NAME}-find-fields
LAMBDA_SQL_GENERATOR=${STACK_NAME}-sql-generator
LAMBDA_BCBS_CLASSIFIER=${STACK_NAME}-bcbs-classifier

# ── ECS ──
ECS_CLUSTER=${STACK_NAME}
ECS_SERVICE=${STACK_NAME}

# ── AWS ──
AWS_REGION=${AWS_REGION}
AWS_ACCOUNT_ID=${ACCOUNT_ID}
ENV_EOF

echo ""
echo "============================================================"
echo ""
echo "  Next steps:"
echo "  ┌─────────────────────────────────────────────────────────┐"
echo "  │ 1. Copy the .env.example above to .env.local            │"
echo "  │ 2. Build and push Docker images to ECR:                  │"
echo "  │    cd ${HOME}/Documents/PwC/dqc-poc                     │"
echo "  │    docker build -t ${STACK_NAME}-api:latest .            │"
echo "  │    docker tag ${STACK_NAME}-api:latest ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${STACK_NAME}-api:latest"
echo "  │    docker push ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${STACK_NAME}-api:latest"
echo "  │                                                         │"
echo "  │    docker build -t ${STACK_NAME}-dqc:latest ./DQC/studio/"
echo "  │    docker tag ${STACK_NAME}-dqc:latest ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${STACK_NAME}-dqc:latest"
echo "  │    docker push ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${STACK_NAME}-dqc:latest"
echo "  │                                                         │"
echo "  │ 3. Force ECS redeploy:                                   │"
echo "  │    aws ecs update-service \\                               │"
echo "  │      --cluster ${STACK_NAME} \\                           │"
echo "  │      --service ${STACK_NAME} \\                           │"
echo "  │      --force-new-deployment                              │"
echo "  │                                                         │"
echo "  │ 4. Test API endpoints:                                   │"
echo "  │    curl ${API_URL}/health                                │"
echo "  │    curl -X POST ${API_URL}/fields \\                     │"
echo "  │      -H 'Content-Type: application/json' \\              │"
echo "  │      -d '{\"project_id\":\"test\",\"rule\":\"test rule\"}'"
echo "  │                                                         │"
echo "  │ 5. Open DQC Studio: http://<ALB_DNS>                    │"
echo "  └─────────────────────────────────────────────────────────┘"
echo ""
echo "  To destroy: ./deploy.sh --destroy --confirm"
echo "============================================================"