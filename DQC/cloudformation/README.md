# DQC PoC — CloudFormation Backend Setup

Automated AWS infrastructure for the DQC (Data Quality Check) generator using native CloudFormation.

## Resolved Defects (GitHub Issues)

| Issue | Title | Resolution |
|---|---|---|
| **#8** | Crear los scripts de CloudFormation | This directory — two stacked templates (infrastructure + serverless) |
| **#4** | Configurar el backend de AWS | ECS Fargate + ALB + API Gateway → Bedrock integration |
| **#5** | API para Nova Micro via .env | API Gateway REST API (`/fields`, `/generate`, `/judge`, `/bcbs`) |
| **#6** | Crear el S3 principal | Versioned, encrypted S3 bucket for prompts, rules, anonymized data |
| **#7** | Lambda #7 — encontrar campos implicados | LangChain Lambda layer + `find-fields` function calling Bedrock |
| **#9** | Lambda #9 — generar query SQL | Retry loop (max 5) + LLM-as-judge evaluation |
| **#10** | DynamoDB para DQCs por proyecto | Table with PK=report_id (project), SK=report_sort (dqc_id) |
| **#2** | Clasificación BCBS 239 | `bcbs-classifier` Lambda with DynamoDB stream trigger |
| **#1** | LLM identifica por qué no es correcto | `validation_failed_reason` field in every DQC output |

## Directory Structure

```
DQC/cloudformation/
├── deploy.sh                          # Main deployment script
├── dqc-infrastructure.yaml            # Stage 1: ECS, ECR, ALB, S3, DynamoDB, IAM
├── dqc-serverless.yaml                # Stage 2: Lambda, API Gateway, Layers
├── .env.example                       # .env template with all CloudFormation outputs
├── README.md                          # This file
│
├── data/
│   ├── prompts/
│   │   ├── fields_prompt.md           # Prompt for field identification (Issue #7)
│   │   ├── sql_prompt.md              # Prompt for SQL generation (Issue #9)
│   │   └── judge_prompt.md            # Prompt for LLM-as-judge (Issue #9)
│   ├── rules/
│   │   └── sample_rules.txt           # Sample DQC rules
│   └── anonymized/
│       └── sample_data.json           # Sample anonymized test data
│
├── lambda-layers/
│   └── langchain-layer/
│       ├── requirements.txt           # LangChain, boto3, pydantic deps
│       └── src/                       # Built layer (python/)
│
└── lambda-functions/
    ├── find-fields/
    │   ├── handler.py                 # Issue #7: Find implicated fields
    │   └── requirements.txt
    ├── sql-generator/
    │   ├── handler.py                 # Issue #9: SQL generation + retry + judge
    │   └── requirements.txt
    └── bcbs-classifier/
        ├── handler.py                 # Issue #2: BCBS 239 classification
        └── requirements.txt
```

## Deployment

### Prerequisites

1. AWS CLI configured (`aws configure` or `aws configure sso`)
2. Python 3.9+ for the Lambda layer builds, on PATH as `python3`, `python` or
   `py -3`. The scripts probe each by *running* it, so the Windows Store alias
   stub is skipped automatically — see Troubleshooting if it still trips.
3. IAM permissions to create: ECS, ECR, Lambda, API Gateway, DynamoDB, S3, IAM roles
4. **Bedrock model access** for Amazon Nova Micro *and* Nova Pro, enabled in the
   target region (console → Bedrock → Model access). Without it every Lambda
   fails with `AccessDeniedException`. The default model ids are the EU
   inference profiles (`eu.amazon.nova-*`), so the region must be an EU one.

### Quick Start

```bash
cd DQC/cloudformation
chmod +x deploy.sh

# Default: S3 + DynamoDB + the three Lambdas behind API Gateway.
# No VPC, no container images, no ECS.
./deploy.sh --region eu-west-1 --stack-name dqc-poc
```

That is the whole deployment for the Lambda work (Issues #7, #9, #2, #10, #6,
#5, #1). The Lambda stack imports only `S3BucketName`, `S3BucketArn`,
`DqcStoreTableName`, `DqcStoreTableArn` and `DqcStoreStreamArn` from stage 1 —
nothing from ECS, ECR or the ALB.

### Adding the container half (Issue #4) — optional

`--with-ecs` additionally deploys ECS Fargate + ECR + ALB, which serve the
FastAPI backend and the DQC Studio UI. This is the only part that needs a VPC:

```bash
./deploy.sh --region eu-west-1 --stack-name dqc-poc --with-ecs \
  --vpc-id vpc-xxxxxxxxxxxxxxxxx \
  --subnet-ids subnet-xxxx,subnet-yyyy
```

`--vpc-id` / `--subnet-ids` are also readable from the `VPC_ID` / `SUBNET_IDS`
environment variables. Windows: `deploy.ps1 -WithEcs -VpcId ... -SubnetIds ...`.

The VPC and subnets are resolved automatically, in this order:

1. `--vpc-id` / `--subnet-ids` if you passed them
2. the account's **default VPC**, if it has one
3. otherwise the **existing VPC whose subnets cover the most AZs** (the ALB needs
   two), breaking ties toward the one with the most public subnets

Subnets are then picked one per AZ, preferring public ones since the ALB is
internet-facing; the script warns if it could only find private subnets. To see
what it has to choose from:

```bash
aws ec2 describe-vpcs --region eu-west-1 \
  --query 'Vpcs[].[VpcId,CidrBlock,IsDefault,Tags[?Key==`Name`]|[0].Value]' --output table

aws ec2 describe-subnets --region eu-west-1 \
  --query 'Subnets[].[VpcId,SubnetId,AvailabilityZone,CidrBlock,MapPublicIpOnLaunch]' --output table
```

If nothing is resolvable the script **exits** and prints that first table for
you — it never calls `ec2:CreateDefaultVpc`.

The ECS service is created with `EcsDesiredCount=0`, because the task definition
pulls `:latest` from ECR repos that this same stack creates empty. At
`DesiredCount: 1` the tasks cannot pull an image, the service never reaches
steady state, and CloudFormation rolls the whole stack back — taking the S3
bucket and DynamoDB table with it. So: deploy, push images, then scale up.

```bash
aws ecr get-login-password --region eu-west-1 \
  | docker login --username AWS --password-stdin <account>.dkr.ecr.eu-west-1.amazonaws.com
docker build -t dqc-poc-api . && docker push <account>.dkr.ecr.eu-west-1.amazonaws.com/dqc-poc-api:latest
docker build -t dqc-poc-dqc ./DQC/studio/ && docker push <account>.dkr.ecr.eu-west-1.amazonaws.com/dqc-poc-dqc:latest

aws ecs update-service --cluster dqc-poc --service dqc-poc \
  --desired-count 1 --force-new-deployment --region eu-west-1
```

### What the deploy does

| Stage | Action |
|---|---|
| 0 | Builds the LangChain layer and each function bundle into `.build/`, using `manylinux2014_x86_64` / cp312 wheels so native deps match the Lambda runtime |
| 1 | `aws cloudformation deploy` of `dqc-infrastructure.yaml` (S3 + DynamoDB + IAM; ECS/ECR/ALB only with `--with-ecs`) |
| 2 | `aws cloudformation package` (uploads `.build/` artifacts to the stack's S3 bucket, rewrites the local paths) then `deploy` of `dqc-serverless.yaml` |
| 3 | Syncs `data/prompts`, `data/rules` and `data/anonymized` to that same bucket |

Stage 2 must run `package` first: the templates reference local directories, and
plain `deploy` cannot upload them. The built layer is ~59 MB zipped, which is
over the 50 MB direct-upload limit and precisely why it goes via S3.

### Destroy

```bash
./deploy.sh --destroy --confirm
```

### What Gets Deployed

**Stage 1 — Infrastructure** (`dqc-infrastructure.yaml`), always:
- S3 bucket (versioned, encrypted, lifecycle policies)
- DynamoDB table (PK: `report_id` = project, SK: `report_sort` = dqc_id) with
  a `NEW_AND_OLD_IMAGES` stream and the `DqcStatusIndex` GSI
- IAM role for Lambda execution

Only with `--with-ecs` (`DeployEcs=true`):
- ECS Cluster + Fargate Service (2 containers: API + DQC Studio), `DesiredCount=0`
- ECR repositories (`dqc-poc-api`, `dqc-poc-dqc`)
- Application Load Balancer (HTTP, internet-facing)
- CloudWatch log group + alarms
- IAM roles (ECS exec, ECS task)
- Security groups (ALB, ECS task)

**Stage 2 — Serverless** (`dqc-serverless.yaml`):
- Lambda layer: LangChain + Bedrock (Python 3.12)
- Lambda: `find-fields` — identifies implicated fields from rules (Issue #7)
- Lambda: `sql-generator` — generates SQL with retry loop (max 5) + LLM-as-judge (Issue #9)
- Lambda: `bcbs-classifier` — BCBS 239 classification (Issue #2)
- API Gateway REST API: `/fields`, `/generate`, `/judge`, `/bcbs`, `/health`, `/checks`, `/dashboard`
- DynamoDB stream trigger for auto-classification

## API Endpoints

After deployment, the API Gateway exposes:

| Endpoint | Method | Lambda | Description |
|---|---|---|---|
| `/health` | GET | — | Health check |
| `/fields` | POST | `find-fields` | Find implicated fields (Issue #7) |
| `/generate` | POST | `sql-generator` | Generate SQL check (Issue #9) |
| `/judge` | POST | `sql-generator` | LLM-as-judge evaluation |
| `/bcbs` | POST | `bcbs-classifier` | BCBS 239 classification (Issue #2) |
| `/checks` | GET | — | List DQC checks (DynamoDB query) |
| `/dashboard` | GET | — | DQC dashboard data |

### Example: Find Implicated Fields

```bash
curl -X POST https://<api-id>.execute-api.eu-west-1.amazonaws.com/prod/fields \
  -H 'Content-Type: application/json' \
  -d '{
    "project_id": "proj_001",
    "rule": "Genera un DQC que verifique que PD_ESTIMADA no sea negativa.",
    "fields_context": "Tabla: exposiciones\n- PD_ESTIMADA: NUMBER - Probabilidad de incumplimiento estimada\n- PD_REAL: NUMBER - Probabilidad real",
    "table_name": "exposiciones"
  }'
```

### Example: Generate SQL

```bash
curl -X POST https://<api-id>.execute-api.eu-west-1.amazonaws.com/prod/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "project_id": "proj_001",
    "rule": "Genera un DQC que verifique que PD_ESTIMADA no sea negativa.",
    "fields": [{"name": "PD_ESTIMADA", "reason": "Campo principal de la regla"}],
    "table_name": "exposiciones",
    "sql_dialect": "postgres"
  }'
```

## Local Development

After deploying the CloudFormation stack, copy the `.env.example` to `.env.local`:

```bash
cp .env.example .env.local
```

Update the values with the CloudFormation outputs, then use the API Gateway URLs in your application configuration.

## Architecture

```
                                              ┌─────────────────────────────┐
                                              │     API Gateway             │
                                              │   (Issues #4, #5)           │
                                              │                             │
         ┌──────────────┐                     │  /fields   → find-fields      │
         │   DQC Studio  │  ← HTTP from ALB  │  /generate → sql-generator    │
         │  (Angular/SPA)│                   │  /judge    → sql-generator    │
         └──────────────┘                     │  /bcbs     → bcbs-classifier  │
                                              └─────────────────────────────┘
                                                     │        │        │
                            ┌────────────────────────┘        │        │
                            │                                 ▼        ▼
                  ┌─────────▼─────────┐        ┌──────────┐ ┌──────────┐
                  │  ECS Fargate      │        │ Lambda:  │ │ Lambda:  │
                  │  (API + DQC UI)   │        │ find-    │ │ sql-     │
                  │                   │        │ fields   │ │ generator│
                  │  REGLLM_LLM=      │        └──────────┘ └──────────┘
                  │  bedrock          │                     │
                  └───────────────────┘                     ▼
                                                    ┌──────────┐
                                                    │ Lambda:  │
                                                    │ bcbs-    │
                                                    │ classifier│
                                                    └──────────┘
                                                         │
                    ┌─────────────────┐                   │
                    │ S3 Bucket       │←── DynamoDB Stream│ (auto-classify)
                    │ (Issues #6)     │                   │
                    │ - prompts/      │                   │
                    │ - rules/        │                   │
                    │ - anonymized/   │                   │
                    └─────────────────┘                   │
                                                         ▼
                                                    ┌──────────────┐
                                                    │ DynamoDB     │
                                                    │ DQC Store    │
                                                    │ (Issue #10)  │
                                                    │ PK: report_id│
                                                    │ SK: report_  │
                                                    │   sort       │
                                                    └──────────────┘
```

## Troubleshooting

### "ERROR: pip's dependency resolver does not currently take into account..."
Harmless, and not actually an error — pip exits 0 and the bundle is correct.
With `--target`, pip still validates its resolution against the *ambient*
site-packages, so anything pinned there (typically a pip-installed `awscli`
holding an older `botocore`) is reported as a conflict even though it is not
part of the Lambda bundle. The scripts pass `--no-warn-conflicts` to silence it.
A genuine pip failure is now printed in full and aborts the deploy.

### "No se encontró Python" / "Python was not found"
On Windows, `WindowsApps\python3.exe` is an app-execution alias that prints this
and exits, even when a real Python is installed as `python`. The scripts detect
and skip it. If you hit it anyway, either turn the alias off (Settings → Apps →
App execution aliases → `python.exe` / `python3.exe`) or name the interpreter:

```bash
PYTHON_BIN=python ./deploy.sh --region eu-west-1 --stack-name dqc-poc
```
```powershell
.\deploy.ps1 -PythonBin C:\Python312\python.exe
```

### Lambda layer size
The layer is ~177 MB unzipped (numpy and botocore dominate). Lambda's hard limit
is 250 MB unzipped for the function plus all its layers, so there is headroom but
not a lot — check before adding dependencies.

### Lambda cold starts
Lambda functions use LangChain which can cause 30-60s cold starts. Use provisioned concurrency or expect initial latency.

### Bedrock model not enabled
Enable Amazon Nova Micro/Pro in Bedrock → Model Access in the AWS console.

### Stack creation fails on IAM
The stack requires `CAPABILITY_IAM` and `CAPABILITY_NAMED_IAM` — this is normal for CloudFormation that creates IAM roles.

### "The security token included in the request is invalid" (InvalidClientTokenId)
Usually not a credential problem. AWS reports a **disabled opt-in region** with
this message, so valid long-lived keys fail in `eu-south-1`/`eu-south-2`,
`me-*`, `af-*`, `ap-east-*` and `il-*` while working everywhere else. Check:

```bash
aws sts get-caller-identity --region us-east-1     # always-enabled control
aws sts get-caller-identity --region <your region> # the one that fails
aws account list-regions --region-opt-status-contains ENABLED ENABLED_BY_DEFAULT \
  --query 'Regions[].RegionName' --output text
```

If `us-east-1` works and the other does not, the region is not enabled — pick
an enabled one or turn it on under Console → Account → AWS Regions. If
`us-east-1` fails too, the credentials really are bad or expired (`aws sso
login`). `deploy.sh` now makes this check up front and prints the enabled list.

Note the Nova defaults are EU inference profiles (`eu.amazon.nova-*`), which
require an **enabled EU region** — `eu-west-1` is the tested one.

### VPC/subnet issues
Only `--with-ecs` needs a VPC — the Lambda deployment does not. The deploy script
never creates networking, so pass `--vpc-id` and `--subnet-ids` explicitly. The subnets must be in the given VPC and span at least two AZs, or
the ALB cannot be created — the script checks this before touching CloudFormation.

### Lambda timeout
Increase timeout in the CloudFormation template (`Timeout: 900` is 15 minutes — sufficient for Bedrock calls).

## Cleanup

To tear down all resources:

```bash
./deploy.sh --destroy --confirm
```

This deletes both the serverless and infrastructure stacks, plus all associated resources (ECR repos are auto-empty on delete, S3 has lifecycle policies but active objects remain — manually delete S3 content if needed).