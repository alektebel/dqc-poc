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
#   ./deploy.sh [--region eu-west-1] [--stack-name dqc-poc] [--with-ecs] \
#              [--vpc-id vpc-xxx] [--subnet-ids subnet-a,subnet-b] [--destroy] [--confirm]
#
# By default this deploys S3 + DynamoDB + the three Lambdas behind API Gateway.
# That path needs no VPC and no container images.
#
# --with-ecs additionally deploys the ECS/ECR/ALB half (Issue #4) that serves the
# FastAPI backend and DQC Studio UI. Only that half needs a VPC, and its service
# starts at DesiredCount=0 because the images do not exist until you push them.
#
# Prerequisites:
#   - AWS CLI configured (aws configure or SSO)
#   - Python 3.9+ on PATH as python3, python or py (override with PYTHON_BIN=...)
#   - Bedrock model access for Nova Micro + Nova Pro in the target region
#   - --with-ecs only: an EXISTING VPC with 2+ subnets in different AZs. This
#     script never creates networking.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_NAME="${STACK_NAME:-dqc-poc}"
AWS_REGION="${AWS_REGION:-eu-west-1}"
CONFIRM="${CONFIRM:-false}"
DESTROY="${DESTROY:-false}"
WITH_ECS="${WITH_ECS:-false}"
PYTHON_BIN="${PYTHON_BIN:-}"
VPC_ID="${VPC_ID:-}"
SUBNET_CSV="${SUBNET_IDS:-}"

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
    --with-ecs)
      WITH_ECS=true
      shift
      ;;
    --vpc-id)
      VPC_ID="$2"
      shift 2
      ;;
    --subnet-ids)
      SUBNET_CSV="$2"
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
      echo "Usage: $0 [--region eu-west-1] [--stack-name dqc-poc] [--with-ecs] \\"
      echo "          [--vpc-id vpc-xxx] [--subnet-ids subnet-a,subnet-b] [--destroy] [--confirm]"
      echo ""
      echo "Options:"
      echo "  --region       AWS region (default: eu-west-1)"
      echo "  --stack-name   CloudFormation stack name (default: dqc-poc)"
      echo "  --with-ecs     Also deploy the ECS/ECR/ALB half (Issue #4). Needs a VPC"
      echo "                 and container images pushed to ECR. Off by default."
      echo "  --vpc-id       Existing VPC (--with-ecs only; default: the account default VPC)"
      echo "  --subnet-ids   Comma-separated subnets, 2+ AZs (--with-ecs only)"
      echo "  --destroy      Destroy the stack instead of deploying"
      echo "  --confirm      Skip confirmation prompt"
      echo "  -h, --help     Show this help"
      echo ""
      echo "Default (no --with-ecs) deploys S3 + DynamoDB + Lambdas + API Gateway,"
      echo "which needs no VPC at all. This script never creates a VPC."
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

# ── VPC / subnet resolution (never creates networking) ────────────────
# Only the ECS/ALB half needs a VPC; the Lambda path skips this entirely.
if [[ "${WITH_ECS}" == "true" ]] && [[ "${DESTROY}" != "true" ]]; then
  echo "==> Resolving VPC and subnets..."

  VPC_SOURCE="--vpc-id"

  # 1. A default VPC, if the account has one.
  if [[ -z "${VPC_ID}" ]]; then
    VPC_ID=$(aws ec2 describe-vpcs \
      --region "${AWS_REGION}" \
      --filters "Name=isDefault,Values=true" \
      --query 'Vpcs[0].VpcId' --output text 2>/dev/null || echo "")
    [[ "${VPC_ID}" == "None" ]] && VPC_ID=""
    [[ -n "${VPC_ID}" ]] && VPC_SOURCE="default VPC"
  fi

  # 2. Otherwise auto-select an existing VPC: the one whose subnets cover the
  #    most AZs, since the ALB needs at least two. Ties break toward the VPC
  #    with the most public subnets, because the ALB is internet-facing.
  if [[ -z "${VPC_ID}" ]]; then
    echo "    No default VPC in ${AWS_REGION}; auto-selecting from existing VPCs..."
    VPC_ID=$(aws ec2 describe-subnets \
      --region "${AWS_REGION}" \
      --query 'Subnets[].[VpcId,AvailabilityZone,MapPublicIpOnLaunch]' \
      --output text 2>/dev/null \
      | awk '
          { azs[$1"|"$2] = 1; if ($3 == "True") pub[$1]++ }
          END {
            for (k in azs) { split(k, p, "|"); n[p[1]]++ }
            for (v in n) printf "%d %d %s\n", n[v], pub[v] + 0, v
          }' \
      | sort -k1,1nr -k2,2nr | head -1 | awk '{print $3}')
    [[ -n "${VPC_ID}" ]] && VPC_SOURCE="auto-selected"
  fi

  if [[ -z "${VPC_ID}" ]] || [[ "${VPC_ID}" == "None" ]]; then
    echo ""
    echo "ERROR: No VPC with subnets found in ${AWS_REGION}, and this script does"
    echo "       NOT create one. Pass an existing VPC explicitly:"
    echo ""
    echo "         $0 --region ${AWS_REGION} --stack-name ${STACK_NAME} --with-ecs \\"
    echo "            --vpc-id vpc-xxxxxxxx --subnet-ids subnet-aaaa,subnet-bbbb"
    echo ""
    echo "       VPCs visible to this identity in ${AWS_REGION}:"
    aws ec2 describe-vpcs --region "${AWS_REGION}" \
      --query 'Vpcs[].[VpcId,CidrBlock,IsDefault,Tags[?Key==`Name`]|[0].Value]' \
      --output table 2>/dev/null || echo "       (ec2:DescribeVpcs denied)"
    echo ""
    echo "       Or drop --with-ecs: the Lambdas need no VPC at all."
    exit 1
  fi

  # 3. Subnets: one per AZ, preferring public ones (internet-facing ALB).
  if [[ -z "${SUBNET_CSV}" ]]; then
    SUBNET_CSV=$(aws ec2 describe-subnets \
      --region "${AWS_REGION}" \
      --filters "Name=vpc-id,Values=${VPC_ID}" \
      --query 'Subnets[].[AvailabilityZone,MapPublicIpOnLaunch,SubnetId]' \
      --output text 2>/dev/null \
      | sort -k1,1 -k2,2r | awk '!seen[$1]++ {print $3}' | paste -sd, -)
  fi

  SUBNET_CSV="${SUBNET_CSV// /}"

  if [[ -z "${SUBNET_CSV}" ]] || [[ "${SUBNET_CSV}" == "None" ]]; then
    echo "ERROR: No subnets found in VPC ${VPC_ID} (region ${AWS_REGION})."
    echo "       Pass them explicitly with --subnet-ids subnet-aaaa,subnet-bbbb"
    exit 1
  fi

  # 4. Validate: subnets must be in this VPC and span 2+ AZs for the ALB.
  SUBNET_INFO=$(aws ec2 describe-subnets \
    --region "${AWS_REGION}" \
    --subnet-ids ${SUBNET_CSV//,/ } \
    --query "Subnets[?VpcId=='${VPC_ID}'].[AvailabilityZone,MapPublicIpOnLaunch]" \
    --output text 2>/dev/null || echo "")

  AZ_COUNT=$(echo "${SUBNET_INFO}" | awk 'NF {print $1}' | sort -u | grep -c . || true)
  PUBLIC_COUNT=$(echo "${SUBNET_INFO}" | awk '$2 == "True"' | grep -c . || true)

  if [[ "${AZ_COUNT}" -lt 2 ]]; then
    echo "ERROR: The Application Load Balancer needs subnets in at least 2 AZs."
    echo "       VPC ${VPC_ID} resolved to: ${SUBNET_CSV} (${AZ_COUNT} AZ)."
    echo "       Subnets in ${VPC_ID}:"
    aws ec2 describe-subnets --region "${AWS_REGION}" \
      --filters "Name=vpc-id,Values=${VPC_ID}" \
      --query 'Subnets[].[SubnetId,AvailabilityZone,CidrBlock,MapPublicIpOnLaunch]' \
      --output table 2>/dev/null || true
    exit 1
  fi

  echo "    VPC:     ${VPC_ID} (${VPC_SOURCE}, not created by this script)"
  echo "    Subnets: ${SUBNET_CSV}"
  echo "    AZs:     ${AZ_COUNT}   Public subnets: ${PUBLIC_COUNT}"

  if [[ "${PUBLIC_COUNT}" -eq 0 ]]; then
    echo ""
    echo "    WARNING: none of these subnets auto-assign public IPs. The stack"
    echo "             creates an internet-facing ALB and Fargate tasks with"
    echo "             AssignPublicIp=ENABLED, which need public subnets with an"
    echo "             internet gateway route. Expect the ALB or the image pull"
    echo "             to fail on private-only subnets."
  fi
  echo ""
else
  echo "==> Skipping VPC resolution (Lambda-only deploy; pass --with-ecs to include ECS/ALB)."
  echo ""
fi

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

# ── Resolve a working Python interpreter ───────────────────────────────
# `python3` must be *executed*, not just found: on Windows the WindowsApps
# python3.exe is an app-execution alias that prints "No se encontró Python" /
# "Python was not found" and exits, so `command -v python3` succeeds anyway.
echo "==> Locating Python..."

py_works() {
  # Intentionally unquoted so a value like "py -3" splits into command + args.
  # shellcheck disable=SC2086
  $1 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' > /dev/null 2>&1
}

if [[ -n "${PYTHON_BIN}" ]]; then
  if ! py_works "${PYTHON_BIN}"; then
    echo "ERROR: PYTHON_BIN='${PYTHON_BIN}' is not a working Python 3.9+ interpreter."
    exit 1
  fi
else
  for candidate in python3 python "py -3" py; do
    if py_works "${candidate}"; then
      PYTHON_BIN="${candidate}"
      break
    fi
  done
fi

if [[ -z "${PYTHON_BIN}" ]]; then
  echo ""
  echo "ERROR: No working Python 3.9+ interpreter found."
  echo "       Tried: python3, python, py -3, py"
  echo ""
  echo "       If 'python --version' works but 'python3' does not, you are on"
  echo "       Windows and python3.exe is the Microsoft Store alias stub. Either:"
  echo "         - disable it: Settings > Apps > App execution aliases >"
  echo "           turn off python.exe / python3.exe, or"
  echo "         - run with an explicit interpreter:"
  echo "             PYTHON_BIN=python ./deploy.sh --region ${AWS_REGION}"
  exit 1
fi

# shellcheck disable=SC2086
if ! $PYTHON_BIN -m pip --version > /dev/null 2>&1; then
  echo "ERROR: '${PYTHON_BIN}' has no pip module. Install it with:"
  echo "         ${PYTHON_BIN} -m ensurepip --upgrade"
  exit 1
fi

# shellcheck disable=SC2086
echo "    Using: ${PYTHON_BIN} ($($PYTHON_BIN -c 'import sys; print(sys.version.split()[0])'))"
echo ""

# ── Stage 0: Build Lambda layer ────────────────────────────────────────
# Wheels must match the Lambda runtime (python3.12, x86_64 manylinux), not the
# local interpreter, or native deps like pydantic-core fail to import at runtime.
BUILD_DIR="${SCRIPT_DIR}/.build"
PIP_LAMBDA_ARGS=(
  --platform manylinux2014_x86_64
  --implementation cp
  --python-version 3.12
  --only-binary=:all:
  --upgrade
  # With --target, pip still checks its resolution against the *ambient*
  # site-packages and prints "ERROR: pip's dependency resolver does not
  # currently take into account all the packages that are installed" for
  # anything pinned there (a pip-installed awscli is the usual culprit). It
  # exits 0 and the bundle is correct; the ambient packages are not in it.
  --no-warn-conflicts
  # Byte-compiling would use the LOCAL interpreter, burying .pyc files for the
  # wrong Python version in the bundle. Lambda compiles on first use anyway.
  --no-compile
)

# Run pip quietly, but surface the full output if it actually fails.
pip_install() {
  local log
  log=$(mktemp)
  # shellcheck disable=SC2086
  if ! $PYTHON_BIN -m pip install "$@" "${PIP_LAMBDA_ARGS[@]}" --quiet > "${log}" 2>&1; then
    echo ""
    echo "ERROR: pip install failed:"
    sed 's/^/    /' "${log}"
    rm -f "${log}"
    exit 1
  fi
  rm -f "${log}"
}

rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}/lambda-layers/langchain-layer"

echo "==> Building Lambda layer (LangChain + Bedrock)..."
pip_install -r "${SCRIPT_DIR}/lambda-layers/langchain-layer/requirements.txt" \
  --target "${BUILD_DIR}/lambda-layers/langchain-layer/python"
find "${BUILD_DIR}/lambda-layers" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
echo "    Layer built at .build/lambda-layers/langchain-layer/python"
echo ""

# ── Stage 0b: Build Lambda function bundles ────────────────────────────
# `aws cloudformation package` zips each of these directories, so handler.py and
# any function-specific deps are staged together under .build/.
for func_dir in find-fields sql-generator bcbs-classifier; do
  echo "==> Building Lambda: ${func_dir}..."
  SRC="${SCRIPT_DIR}/lambda-functions/${func_dir}"
  DEST="${BUILD_DIR}/lambda-functions/${func_dir}"
  mkdir -p "${DEST}"

  find "${SRC}" -maxdepth 1 -name '*.py' -exec cp {} "${DEST}/" \;

  # Blank/comment-only requirements mean "everything comes from the layer".
  if [[ -f "${SRC}/requirements.txt" ]] && grep -qE '^[[:space:]]*[^#[:space:]]' "${SRC}/requirements.txt"; then
    pip_install -r "${SRC}/requirements.txt" --target "${DEST}"
  fi

  find "${DEST}" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
  echo "    ${func_dir} staged."
done

cd "${SCRIPT_DIR}"
echo ""

# ── Stage 1: Deploy Infrastructure ─────────────────────────────────────
echo "=== Stage 1: Deploying Infrastructure ==="
echo ""

aws cloudformation deploy \
  --stack-name "${STACK_NAME}-infrastructure" \
  --template-file "${SCRIPT_DIR}/dqc-infrastructure.yaml" \
  --region "${AWS_REGION}" \
  --parameter-overrides \
    ProjectName="${STACK_NAME}" \
    AWSRegion="${AWS_REGION}" \
    DeployEcs="${WITH_ECS}" \
    VpcId="${VPC_ID}" \
    SubnetIds="${SUBNET_CSV}" \
    BedrockModelId=eu.amazon.nova-micro-v1:0 \
    TaskCpu=1024 \
    MemoryMiB=4096 \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset \
  --tags Project=dqc-poc ManagedBy=cloudformation Stage=infrastructure

echo ""

# ── Stage 2: Deploy Serverless ─────────────────────────────────────────
echo "=== Stage 2: Deploying Serverless (Lambda + API Gateway) ==="
echo ""

# The Lambda code and layer live on disk, so the template has to be packaged
# (artifacts uploaded to S3, local paths rewritten) before it can be deployed.
ARTIFACT_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}-infrastructure" \
  --region "${AWS_REGION}" \
  --query "Stacks[0].Outputs[?OutputKey=='S3BucketName'].OutputValue" \
  --output text)

if [[ -z "${ARTIFACT_BUCKET}" ]] || [[ "${ARTIFACT_BUCKET}" == "None" ]]; then
  echo "ERROR: Could not read S3BucketName from the ${STACK_NAME}-infrastructure stack."
  exit 1
fi

echo "    Packaging artifacts to s3://${ARTIFACT_BUCKET}/lambda-artifacts/"
PACKAGED_TEMPLATE="${SCRIPT_DIR}/.dqc-serverless.packaged.yaml"

aws cloudformation package \
  --template-file "${SCRIPT_DIR}/dqc-serverless.yaml" \
  --s3-bucket "${ARTIFACT_BUCKET}" \
  --s3-prefix lambda-artifacts \
  --output-template-file "${PACKAGED_TEMPLATE}" \
  --region "${AWS_REGION}"

aws cloudformation deploy \
  --stack-name "${STACK_NAME}-serverless" \
  --template-file "${PACKAGED_TEMPLATE}" \
  --region "${AWS_REGION}" \
  --parameter-overrides \
    ProjectName="${STACK_NAME}" \
    AWSRegion="${AWS_REGION}" \
    BedrockModelId=eu.amazon.nova-micro-v1:0 \
    JudgeBedrockModelId=eu.amazon.nova-pro-v1:0 \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset \
  --tags Project=dqc-poc ManagedBy=cloudformation Stage=serverless

echo ""

# ── Upload data to S3 ─────────────────────────────────────────────────
echo "=== Uploading Data to S3 ==="
echo ""

# Created by the infrastructure stack (Issue #6) — do not re-create it here.
S3_BUCKET="${ARTIFACT_BUCKET}"
echo "    S3 bucket: ${S3_BUCKET}"

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
echo ""
echo "  Infrastructure (Stage 1):"
echo "    S3 Bucket:      ${S3_BUCKET}"
echo "    DynamoDB Table: ${STACK_NAME}-dqc-store"
echo "    IAM Role:       ${STACK_NAME}-lambda-exec"
if [[ "${WITH_ECS}" == "true" ]]; then
  echo "    ECS Cluster/Service: ${STACK_NAME} (DesiredCount=0 until images are pushed)"
  echo "    ECR Repos:      ${STACK_NAME}-api, ${STACK_NAME}-dqc"
  echo "    ALB:            http://<alb-dns>"
  echo "    IAM Roles:      ${STACK_NAME}-ecs-exec, ${STACK_NAME}-ecs-task"
fi
echo ""
echo "  Serverless (Stage 2):"
echo "    Lambda:       ${STACK_NAME}-find-fields      (Issue #7)"
echo "    Lambda:       ${STACK_NAME}-sql-generator    (Issue #9)"
echo "    Lambda:       ${STACK_NAME}-bcbs-classifier  (Issue #2)"
echo "    API Gateway:  ${STACK_NAME}-dqc-api          (Issues #4, #5)"
echo "    Lambda Layer: ${STACK_NAME}-langchain-layer"
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
echo ""
echo "  1. Copy the .env block above to .env.local"
echo ""
echo "  2. Test the API:"
echo "       curl ${API_URL}/health"
echo "       curl -X POST ${API_URL}/fields \\"
echo "         -H 'Content-Type: application/json' \\"
echo "         -d '{\"project_id\":\"test\",\"rule\":\"PD_ESTIMADA no puede ser negativa\"}'"
echo ""

if [[ "${WITH_ECS}" == "true" ]]; then
  echo "  3. Build and push the container images:"
  echo "       aws ecr get-login-password --region ${AWS_REGION} \\"
  echo "         | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
  echo "       docker build -t ${STACK_NAME}-api ."
  echo "       docker tag ${STACK_NAME}-api ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${STACK_NAME}-api:latest"
  echo "       docker push ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${STACK_NAME}-api:latest"
  echo "       docker build -t ${STACK_NAME}-dqc ./DQC/studio/"
  echo "       docker tag ${STACK_NAME}-dqc ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${STACK_NAME}-dqc:latest"
  echo "       docker push ${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${STACK_NAME}-dqc:latest"
  echo ""
  echo "  4. Scale the service up (it was created at DesiredCount=0 so the stack"
  echo "     could finish before any image existed):"
  echo "       aws ecs update-service --cluster ${STACK_NAME} --service ${STACK_NAME} \\"
  echo "         --desired-count 1 --force-new-deployment --region ${AWS_REGION}"
  echo ""
  echo "  5. Open DQC Studio at http://<ALB_DNS>"
  echo ""
else
  echo "  The ECS/ECR/ALB half (Issue #4 — FastAPI backend + DQC Studio UI) was"
  echo "  not deployed. It is not needed for the Lambdas. To add it later:"
  echo "       ./deploy.sh --region ${AWS_REGION} --stack-name ${STACK_NAME} --with-ecs \\"
  echo "         --vpc-id vpc-xxxx --subnet-ids subnet-aaaa,subnet-bbbb"
  echo ""
fi

echo "  To destroy: ./deploy.sh --destroy --confirm"
echo "============================================================"