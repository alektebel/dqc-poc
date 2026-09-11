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
2. Python 3.11+ (for Lambda layer builds)
3. IAM permissions to create: ECS, ECR, Lambda, API Gateway, DynamoDB, S3, IAM roles
4. **An existing VPC with at least two subnets in different AZs.** Neither the
   templates nor `deploy.sh` create networking — no VPC, subnets, IGW or NAT.
   The ALB requires 2+ AZs, so a single-subnet VPC is rejected up front.
5. **Bedrock model access** for Amazon Nova Micro *and* Nova Pro, enabled in the
   target region (console → Bedrock → Model access). Without it every Lambda
   fails with `AccessDeniedException`. The default model ids are the EU
   inference profiles (`eu.amazon.nova-*`), so the region must be an EU one.

### Quick Start

```bash
cd DQC/cloudformation
chmod +x deploy.sh

# Corporate environment — pass the VPC and subnets you were given:
./deploy.sh --region eu-west-1 --stack-name dqc-poc \
  --vpc-id vpc-xxxxxxxxxxxxxxxxx \
  --subnet-ids subnet-xxxx,subnet-yyyy

# If (and only if) the account has a default VPC, they can be omitted and the
# script will pick one subnet per AZ from it:
./deploy.sh --region eu-west-1 --stack-name dqc-poc
```

`--vpc-id` / `--subnet-ids` are also readable from the `VPC_ID` / `SUBNET_IDS`
environment variables. Windows: `deploy.ps1 -VpcId ... -SubnetIds ...`.

If no VPC is resolved, the script **exits** and prints the VPCs visible to your
identity — it never calls `ec2:CreateDefaultVpc`.

### What the deploy does

| Stage | Action |
|---|---|
| 0 | Builds the LangChain layer and each function bundle into `.build/`, using `manylinux2014_x86_64` / cp312 wheels so native deps match the Lambda runtime |
| 1 | `aws cloudformation deploy` of `dqc-infrastructure.yaml` into the VPC you passed |
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

**Stage 1 — Infrastructure** (`dqc-infrastructure.yaml`):
- ECS Cluster + Fargate Service (2 containers: API + DQC Studio)
- ECR repositories (`dqc-poc-api`, `dqc-poc-dqc`)
- Application Load Balancer (HTTP, internet-facing)
- S3 bucket (versioned, encrypted, lifecycle policies)
- DynamoDB table (PK: `report_id` = project, SK: `report_sort` = dqc_id)
- CloudWatch log group + alarms
- IAM roles (ECS exec, ECS task, Lambda execution)
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

### VPC/subnet issues
The deploy script never creates networking. Pass `--vpc-id` and `--subnet-ids`
explicitly. The subnets must be in the given VPC and span at least two AZs, or
the ALB cannot be created — the script checks this before touching CloudFormation.

### Lambda timeout
Increase timeout in the CloudFormation template (`Timeout: 900` is 15 minutes — sufficient for Bedrock calls).

## Cleanup

To tear down all resources:

```bash
./deploy.sh --destroy --confirm
```

This deletes both the serverless and infrastructure stacks, plus all associated resources (ECR repos are auto-empty on delete, S3 has lifecycle policies but active objects remain — manually delete S3 content if needed).