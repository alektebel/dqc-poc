<#
.SYNOPSIS
    DQC PoC — CloudFormation deployment script (PowerShell / Windows).
    Deploys DQC backend on AWS in two stages:
      Stage 1: Infrastructure (ECS, ECR, ALB, S3, DynamoDB, IAM)
      Stage 2: Serverless (Lambda, API Gateway, Lambda Layer)
    Resolves defects: #4, #5, #6, #7, #8, #9, #10, #2, #1
.DESCRIPTION
    Runs on Windows (PowerShell 5.1 / 7+). Requires:
      - AWS CLI configured  (aws configure  or  aws configure sso)
      - Python 3.11+       (for Lambda layer builds)
      - Coreutils zip/unzip  (Git Bash ships with zip, or install 7-Zip)
.PARAMETER Region
    AWS region (default: eu-west-1).
.PARAMETER StackName
    CloudFormation stack name (default: dqc-poc).
.PARAMETER Destroy
    Destroy the stack instead of deploying.
.PARAMETER Confirm
    Skip the confirmation prompt on destroy.
.EXAMPLE
    .\deploy.ps1 -Region eu-west-1 -StackName dqc-poc
    .\deploy.ps1 -Destroy -Confirm
    .\deploy.ps1 -Region eu-west-1 -StackName my-dqc

    Deploys S3 + DynamoDB + the three Lambdas behind API Gateway. No VPC and no
    container images are needed for that path.

    .\deploy.ps1 -Region eu-west-1 -StackName my-dqc -WithEcs ``
        -VpcId vpc-xxxx -SubnetIds subnet-aaaa,subnet-bbbb

    Adds the ECS/ECR/ALB half (Issue #4). Requires an EXISTING VPC with 2+
    subnets in different AZs. This script never creates networking.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string] $Region = "eu-west-1",

    [Parameter(Mandatory = $false)]
    [string] $StackName = "dqc-poc",

    [Parameter(Mandatory = $false)]
    [switch] $Destroy,

    [Parameter(Mandatory = $false)]
    [switch] $Confirm,

    [Parameter(Mandatory = $false)]
    [string] $VpcId = "",

    [Parameter(Mandatory = $false)]
    [string] $SubnetIds = "",

    [switch] $WithEcs
)

$ErrorActionPreference = "Stop"

# ── Helpers ────────────────────────────────────────────────────────────
function Write-Step { param($Msg) Write-Host "`n==> $Msg" -ForegroundColor Cyan }
function Write-Block { param($Msg) Write-Host "`n=== $Msg ===" -ForegroundColor Magenta }

function Invoke-Aws {
    param($Args)
    & aws @Args 2>&1
    if ($LASTEXITCODE -ne 0) { throw "aws command failed: aws @Args" }
}

function Test-AwsCredentials {
    try {
        aws sts get-caller-identity --query 'Arn' --output text 2>$null | Out-Null
        return $true
    } catch {
        return $false
    }
}


# Detect script directory (works in PS5 and PS7)
$PSScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path $MyInvocation.MyCommand.Path -Parent }

# ── Header ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  DQC PoC — CloudFormation Deployment (PowerShell / Windows)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ── Verify AWS credentials ────────────────────────────────────────────
Write-Step "Verifying AWS credentials..."
if (-not (Test-AwsCredentials)) {
    Write-Host "ERROR: AWS credentials not configured. Run:" -ForegroundColor Red
    Write-Host "  aws configure   (or  aws configure sso)" -ForegroundColor Red
    exit 1
}

try {
    $account = aws sts get-caller-identity --query 'Account' --output text 2>$null
} catch {
    $account = "unknown"
}

Write-Host "    Account: $($account.PadRight(12))  Region: $($Region.PadRight(12))  Stack: $($StackName)"
Write-Host ""

# ── VPC / subnet resolution (never creates networking) ────────────────
# Only the ECS/ALB half needs a VPC; the Lambda path skips this entirely.
if ($WithEcs -and -not $Destroy) {
    Write-Step "Resolving VPC and subnets..."

    $vpcSource = "-VpcId"

    # 1. A default VPC, if the account has one.
    if (-not $VpcId) {
        try {
            $VpcId = aws ec2 describe-vpcs `
                --region $Region `
                --filters "Name=isDefault,Values=true" `
                --query 'Vpcs[0].VpcId' --output text 2>$null
        } catch { $VpcId = "" }
        if ($VpcId -eq "None") { $VpcId = "" }
        if ($VpcId) { $vpcSource = "default VPC" }
    }

    # Subnet inventory for the region, reused for selection and validation.
    $allSubnets = @()
    try {
        $rows = aws ec2 describe-subnets `
            --region $Region `
            --query 'Subnets[].[VpcId,AvailabilityZone,MapPublicIpOnLaunch,SubnetId]' `
            --output text 2>$null
        $allSubnets = @($rows -split "`n" | Where-Object { $_.Trim() } | ForEach-Object {
            $p = $_ -split "`t"
            [PSCustomObject]@{
                VpcId    = $p[0]
                AZ       = $p[1]
                IsPublic = ($p[2] -eq "True")
                SubnetId = $p[3]
            }
        })
    } catch { $allSubnets = @() }

    # 2. Otherwise auto-select: the VPC whose subnets cover the most AZs, since
    #    the ALB needs at least two. Ties break toward the most public subnets.
    if (-not $VpcId) {
        Write-Host "    No default VPC in $($Region); auto-selecting from existing VPCs..."
        $best = $allSubnets | Group-Object VpcId | ForEach-Object {
            [PSCustomObject]@{
                VpcId     = $_.Name
                AzCount   = ($_.Group | Select-Object -ExpandProperty AZ -Unique).Count
                PubCount  = ($_.Group | Where-Object IsPublic).Count
            }
        } | Sort-Object AzCount, PubCount -Descending | Select-Object -First 1

        if ($best) { $VpcId = $best.VpcId; $vpcSource = "auto-selected" }
    }

    if (-not $VpcId -or $VpcId -eq "None") {
        Write-Host ""
        Write-Host "ERROR: No VPC with subnets found in $($Region), and this script does" -ForegroundColor Red
        Write-Host "       NOT create one. Pass an existing VPC explicitly:" -ForegroundColor Red
        Write-Host ""
        Write-Host "         .\deploy.ps1 -Region $Region -StackName $StackName -WithEcs ``" -ForegroundColor Yellow
        Write-Host "            -VpcId vpc-xxxxxxxx -SubnetIds subnet-aaaa,subnet-bbbb" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "       VPCs visible to this identity in $($Region):" -ForegroundColor Red
        aws ec2 describe-vpcs --region $Region `
            --query 'Vpcs[].[VpcId,CidrBlock,IsDefault,Tags[?Key==`Name`]|[0].Value]' `
            --output table 2>$null
        Write-Host ""
        Write-Host "       Or drop -WithEcs: the Lambdas need no VPC at all." -ForegroundColor Yellow
        exit 1
    }

    # 3. Subnets: one per AZ, preferring public ones (internet-facing ALB).
    if (-not $SubnetIds) {
        $picked = $allSubnets | Where-Object { $_.VpcId -eq $VpcId } |
            Group-Object AZ | ForEach-Object {
                ($_.Group | Sort-Object IsPublic -Descending | Select-Object -First 1).SubnetId
            }
        $SubnetIds = (@($picked) -join ",")
    }

    $SubnetIds = $SubnetIds -replace "\s", ""

    if (-not $SubnetIds) {
        Write-Host "ERROR: No subnets found in VPC $($VpcId) (region $($Region))." -ForegroundColor Red
        Write-Host "       Pass them explicitly with -SubnetIds subnet-aaaa,subnet-bbbb" -ForegroundColor Red
        exit 1
    }

    # 4. Validate: subnets must be in this VPC and span 2+ AZs for the ALB.
    $chosen = @($allSubnets | Where-Object { $_.VpcId -eq $VpcId -and ($SubnetIds -split ",") -contains $_.SubnetId })
    $azCount = ($chosen | Select-Object -ExpandProperty AZ -Unique).Count
    $publicCount = ($chosen | Where-Object IsPublic).Count

    if ($azCount -lt 2) {
        Write-Host "ERROR: The Application Load Balancer needs subnets in at least 2 AZs." -ForegroundColor Red
        Write-Host "       VPC $($VpcId) resolved to: $($SubnetIds) ($($azCount) AZ)." -ForegroundColor Red
        Write-Host "       Subnets in $($VpcId):" -ForegroundColor Red
        aws ec2 describe-subnets --region $Region `
            --filters "Name=vpc-id,Values=$VpcId" `
            --query 'Subnets[].[SubnetId,AvailabilityZone,CidrBlock,MapPublicIpOnLaunch]' `
            --output table 2>$null
        exit 1
    }

    Write-Host "    VPC:     $($VpcId) ($($vpcSource), not created by this script)"
    Write-Host "    Subnets: $($SubnetIds)"
    Write-Host "    AZs:     $($azCount)   Public subnets: $($publicCount)"

    if ($publicCount -eq 0) {
        Write-Host ""
        Write-Host "    WARNING: none of these subnets auto-assign public IPs. The stack" -ForegroundColor Yellow
        Write-Host "             creates an internet-facing ALB and Fargate tasks with" -ForegroundColor Yellow
        Write-Host "             AssignPublicIp=ENABLED, which need public subnets with an" -ForegroundColor Yellow
        Write-Host "             internet gateway route." -ForegroundColor Yellow
    }
    Write-Host ""
}

# ── Destroy mode ──────────────────────────────────────────────────────
if ($Destroy) {
    Write-Host "`n==> Destroying stack: $($StackName)" -ForegroundColor Yellow

    if (-not $Confirm) {
        $answer = Read-Host "Are you sure you want to destroy the stack? This will delete all resources. [y/N]"
        if ($answer -notin @("y", "Y")) {
            Write-Host "Aborted."
            exit 0
        }
    }

    # Destroy serverless first (depends on infrastructure)
    Write-Host "    [1/2] Destroying serverless stack..."
    aws cloudformation delete-stack --stack-name "$StackName-serverless" --region $Region 2>$null
    aws cloudformation wait stack-delete-complete --stack-name "$StackName-serverless" --region $Region 2>$null

    Write-Host "    [2/2] Destroying infrastructure stack..."
    aws cloudformation delete-stack --stack-name "$StackName-infrastructure" --region $Region
    aws cloudformation wait stack-delete-complete --stack-name "$StackName-infrastructure" --region $Region

    # Also delete main stack if it exists
    aws cloudformation delete-stack --stack-name "$StackName" --region $Region 2>$null

    Write-Host "`n✓ Stack destroyed." -ForegroundColor Green
    exit 0
}

# ── Stage 0: Build Lambda Layer ───────────────────────────────────────
# Wheels must match the Lambda runtime (python3.12, x86_64 manylinux), not the
# local interpreter, or native deps like pydantic-core fail to import at runtime.
Write-Step "Building Lambda layer (LangChain + Bedrock)..."

$buildDir = Join-Path $PSScriptDir ".build"
$pipLambdaArgs = @(
    "--platform", "manylinux2014_x86_64",
    "--implementation", "cp",
    "--python-version", "3.12",
    "--only-binary=:all:",
    "--upgrade"
)

if (Test-Path $buildDir) { Remove-Item $buildDir -Recurse -Force }

$layerDir = Join-Path $PSScriptDir "lambda-layers\langchain-layer"
if (-not (Test-Path $layerDir)) {
    Write-Host "ERROR: Directory not found: $layerDir" -ForegroundColor Red
    exit 1
}

$layerTarget = Join-Path $buildDir "lambda-layers\langchain-layer\python"
New-Item -ItemType Directory -Force -Path $layerTarget | Out-Null
python -m pip install -r (Join-Path $layerDir "requirements.txt") -t $layerTarget @pipLambdaArgs --quiet
Write-Host "    Layer built at .build\lambda-layers\langchain-layer\python"

# ── Stage 0b: Build Lambda function bundles ────────────────────────────
# `aws cloudformation package` zips each of these directories, so handler.py and
# any function-specific deps are staged together under .build\.
$funcDirs = @("find-fields", "sql-generator", "bcbs-classifier")

foreach ($funcDir in $funcDirs) {
    Write-Step "Building Lambda: $funcDir..."
    $funcPath = Join-Path $PSScriptDir "lambda-functions" $funcDir
    if (-not (Test-Path $funcPath)) {
        Write-Host "    WARNING: Directory not found: $funcPath — skipping." -ForegroundColor Yellow
        continue
    }

    $funcTarget = Join-Path $buildDir "lambda-functions\$funcDir"
    New-Item -ItemType Directory -Force -Path $funcTarget | Out-Null
    Get-ChildItem $funcPath -Filter "*.py" -File | ForEach-Object {
        Copy-Item $_.FullName -Destination $funcTarget -Force
    }

    # Blank/comment-only requirements mean "everything comes from the layer".
    $reqFile = Join-Path $funcPath "requirements.txt"
    if ((Test-Path $reqFile) -and (Get-Content $reqFile | Where-Object { $_ -match '^\s*[^#\s]' })) {
        python -m pip install -r $reqFile -t $funcTarget @pipLambdaArgs --quiet
    }

    Write-Host "    $funcDir staged."
}

Write-Host ""

# ── Stage 1: Deploy Infrastructure ─────────────────────────────────────
Write-Block "Stage 1: Deploying Infrastructure (ECS, ECR, ALB, S3, DynamoDB, IAM)"

$infraTemplate = Join-Path $PSScriptDir "dqc-infrastructure.yaml"
$infraArgs = @(
    "cloudformation", "deploy",
    "--stack-name", "$StackName-infrastructure",
    "--template-file", "`"$infraTemplate`"",
    "--region", $Region,
    "--parameter-overrides",
        "ProjectName=$StackName",
        "AWSRegion=$Region",
        "DeployEcs=$(if ($WithEcs) { 'true' } else { 'false' })",
        "VpcId=$VpcId",
        "SubnetIds=$SubnetIds",
        "BedrockModelId=eu.amazon.nova-micro-v1:0",
        "TaskCpu=1024",
        "MemoryMiB=4096",
    "--capabilities", "CAPABILITY_IAM", "CAPABILITY_NAMED_IAM",
    "--no-fail-on-empty-changeset",
    "--tags", "Project=dqc-poc", "ManagedBy=cloudformation", "Stage=infrastructure"
)

Write-Host "    aws $($infraArgs -join ' ')" -ForegroundColor Gray
Write-Host ""
Invoke-Aws -Args $infraArgs
Write-Host ""

# ── Stage 2: Deploy Serverless ─────────────────────────────────────────
Write-Block "Stage 2: Deploying Serverless (Lambda + API Gateway)"

# The Lambda code and layer live on disk, so the template has to be packaged
# (artifacts uploaded to S3, local paths rewritten) before it can be deployed.
$artifactBucket = aws cloudformation describe-stacks `
    --stack-name "$StackName-infrastructure" `
    --region $Region `
    --query "Stacks[0].Outputs[?OutputKey=='S3BucketName'].OutputValue" `
    --output text 2>$null

if (-not $artifactBucket -or $artifactBucket -eq "None") {
    Write-Host "ERROR: Could not read S3BucketName from the $StackName-infrastructure stack." -ForegroundColor Red
    exit 1
}

Write-Host "    Packaging artifacts to s3://$artifactBucket/lambda-artifacts/"

$slTemplate = Join-Path $PSScriptDir "dqc-serverless.yaml"
$packagedTemplate = Join-Path $PSScriptDir ".dqc-serverless.packaged.yaml"

Invoke-Aws -Args @(
    "cloudformation", "package",
    "--template-file", "`"$slTemplate`"",
    "--s3-bucket", $artifactBucket,
    "--s3-prefix", "lambda-artifacts",
    "--output-template-file", "`"$packagedTemplate`"",
    "--region", $Region
)

$slArgs = @(
    "cloudformation", "deploy",
    "--stack-name", "$StackName-serverless",
    "--template-file", "`"$packagedTemplate`"",
    "--region", $Region,
    "--parameter-overrides",
        "ProjectName=$StackName",
        "AWSRegion=$Region",
        "BedrockModelId=eu.amazon.nova-micro-v1:0",
        "JudgeBedrockModelId=eu.amazon.nova-pro-v1:0",
    "--capabilities", "CAPABILITY_IAM", "CAPABILITY_NAMED_IAM",
    "--no-fail-on-empty-changeset",
    "--tags", "Project=dqc-poc", "ManagedBy=cloudformation", "Stage=serverless"
)

Write-Host "    aws $($slArgs -join ' ')" -ForegroundColor Gray
Write-Host ""
Invoke-Aws -Args $slArgs
Write-Host ""

# ── Upload data to S3 ──────────────────────────────────────────────────
Write-Block "Uploading Data to S3"

# Created by the infrastructure stack (Issue #6) — do not re-create it here.
$s3Bucket = $artifactBucket
Write-Host "    S3 bucket: $s3Bucket"

# Upload prompts
Write-Host "    Uploading prompts..."
$promptsDir = Join-Path $PSScriptDir "data\prompts"
if (Test-Path $promptsDir) {
    Get-ChildItem $promptsDir -Filter "*.md" | ForEach-Object {
        $fname = $_.BaseName
        aws s3 cp $_.FullName "s3://$s3Bucket/prompts/$fname.md" --region $Region --quiet 2>$null
    }
}

# Upload rules
Write-Host "    Uploading rules..."
$rulesDir = Join-Path $PSScriptDir "data\rules"
if (Test-Path $rulesDir) {
    Get-ChildItem $rulesDir -Filter "*.txt" | ForEach-Object {
        $fname = $_.Name
        aws s3 cp $_.FullName "s3://$s3Bucket/rules/$fname" --region $Region --quiet 2>$null
    }
}

# Upload anonymized data
Write-Host "    Uploading anonymized data..."
$anonDir = Join-Path $PSScriptDir "data\anonymized"
if (Test-Path $anonDir) {
    Get-ChildItem $anonDir -Filter "*.json" | ForEach-Object {
        $fname = $_.Name
        aws s3 cp $_.FullName "s3://$s3Bucket/anonymized/$fname" --region $Region --quiet 2>$null
    }
}

Write-Host ""

# ── Print outputs ──────────────────────────────────────────────────────
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  DQC PoC — CloudFormation deployment complete!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "  Resources created:" -ForegroundColor White
Write-Host "  +-------------------------------------------------------+" -ForegroundColor White
Write-Host "  | Infrastructure (Stage 1):                             |" -ForegroundColor White
Write-Host "  |   ECS Cluster/Service: $($StackName.PadRight(22))|" -ForegroundColor White
Write-Host "  |   ECR Repos:      $($StackName-api, $StackName-dqc.PadRight(30))|" -ForegroundColor White
Write-Host "  |   ALB:            http://<alb-dns>                  |" -ForegroundColor White
Write-Host "  |   S3 Bucket:      $($s3Bucket.PadRight(25))|" -ForegroundColor White
Write-Host "  |   DynamoDB Table: $($StackName-dqc-store.PadRight(23))|" -ForegroundColor White
Write-Host "  |   IAM Roles:      $($StackName)-ecs-exec, $($StackName)-ecs-task|" -ForegroundColor White
Write-Host "  +-------------------------------------------------------+" -ForegroundColor White
Write-Host ""
Write-Host "  Serverless (Stage 2):" -ForegroundColor White
Write-Host "  +-------------------------------------------------------+" -ForegroundColor White
Write-Host "  |   Lambda: $($StackName)-find-fields        (Issue #7)  |" -ForegroundColor White
Write-Host "  |   Lambda: $($StackName)-sql-generator      (Issue #9)  |" -ForegroundColor White
Write-Host "  |   Lambda: $($StackName)-bcbs-classifier    (Issue #2)  |" -ForegroundColor White
Write-Host "  |   API Gateway: $($StackName)-dqc-api      (Issues #4,#5)|" -ForegroundColor White
Write-Host "  |   Lambda Layer: $($StackName)-langchain-layer            |" -ForegroundColor White
Write-Host "  +-------------------------------------------------------+" -ForegroundColor White
Write-Host ""

# Get API Gateway URL
$apiUrl = ""
try {
    $apiUrl = aws cloudformation describe-stacks `
        --stack-name "$StackName-serverless" `
        --region $Region `
        --query "Stacks[0].Outputs[?OutputKey=='DqcApiUrl'].OutputValue" `
        --output text 2>$null
} catch { $apiUrl = "" }

Write-Host "  .env.example (copy to .env.local):" -ForegroundColor White
Write-Host ""
$envLines = @()
$envLines += "# DQC PoC — CloudFormation outputs (generated for $StackName)"
$envLines += "# Copy this file to .env.local and update values"
$envLines += ""
$envLines += "# ── API Gateway (Issues #4, #5) ──"
$envLines += "DQC_API_URL=$apiUrl"
$envLines += "DQC_API_FIELDS=`${DQC_API_URL}/fields"
$envLines += "DQC_API_GENERATE=`${DQC_API_URL}/generate"
$envLines += "DQC_API_JUDGE=`${DQC_API_URL}/judge"
$envLines += "DQC_API_BCBS=`${DQC_API_URL}/bcbs"
$envLines += "DQC_API_CHECKS=`${DQC_API_URL}/checks"
$envLines += "DQC_API_HEALTH=`${DQC_API_URL}/health"
$envLines += ""
$envLines += "# ── S3 (Issue #6) ──"
$envLines += "DQC_S3_BUCKET=$s3Bucket"
$envLines += "DQC_S3_REGION=$Region"
$envLines += ""
$envLines += "# ── DynamoDB (Issue #10) ──"
$envLines += "DQC_DYNAMODB_TABLE=$StackName-dqc-store"
$envLines += "DQC_DYNAMODB_REGION=$Region"
$envLines += ""
$envLines += "# ── Bedrock ──"
$envLines += "BEDROCK_MODEL_ID=eu.amazon.nova-micro-v1:0"
$envLines += "BEDROCK_JUDGE_MODEL_ID=eu.amazon.nova-pro-v1:0"
$envLines += "BEDROCK_REGION=$Region"
$envLines += ""
$envLines += "# ── Lambda Functions ──"
$envLines += "LAMBDA_FIND_FIELDS=$StackName-find-fields"
$envLines += "LAMBDA_SQL_GENERATOR=$StackName-sql-generator"
$envLines += "LAMBDA_BCBS_CLASSIFIER=$StackName-bcbs-classifier"
$envLines += ""
$envLines += "# ── ECS ──"
$envLines += "ECS_CLUSTER=$StackName"
$envLines += "ECS_SERVICE=$StackName"
$envLines += ""
$envLines += "# ── AWS ──"
$envLines += "AWS_REGION=$Region"
$envLines += "AWS_ACCOUNT_ID=$account"

Write-Host ($envLines -join "`n")
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host "  +-------------------------------------------------------+" -ForegroundColor White
Write-Host "  | 1. Copy the .env.example above to .env.local            |" -ForegroundColor White
Write-Host "  | 2. Build and push Docker images to ECR:                  |" -ForegroundColor White
Write-Host "  |    cd <project-root>                                   |" -ForegroundColor White
Write-Host "  |    docker build -t $StackName-api:latest .             |" -ForegroundColor White
Write-Host "  |    docker tag $StackName-api:latest $account.dkr.ecr.$Region.amazonaws.com/$StackName-api:latest" -ForegroundColor White
Write-Host "  |    docker push $account.dkr.ecr.$Region.amazonaws.com/$StackName-api:latest" -ForegroundColor White
Write-Host "  |                                                         |" -ForegroundColor White
Write-Host "  |    docker build -t $StackName-dqc:latest .\DQC\studio\ |" -ForegroundColor White
Write-Host "  |    docker tag $StackName-dqc:latest $account.dkr.ecr.$Region.amazonaws.com/$StackName-dqc:latest" -ForegroundColor White
Write-Host "  |    docker push $account.dkr.ecr.$Region.amazonaws.com/$StackName-dqc:latest" -ForegroundColor White
Write-Host "  |                                                         |" -ForegroundColor White
Write-Host "  | 3. Force ECS redeploy:                                   |" -ForegroundColor White
Write-Host "  |    aws ecs update-service \`                            |" -ForegroundColor White
Write-Host "  |      --cluster $StackName \`                           |" -ForegroundColor White
Write-Host "  |      --service $StackName \`                           |" -ForegroundColor White
Write-Host "  |      --force-new-deployment                            |" -ForegroundColor White
Write-Host "  |                                                         |" -ForegroundColor White
Write-Host "  | 4. Test API endpoints:                                   |" -ForegroundColor White
Write-Host "  |    curl $apiUrl/health                                 |" -ForegroundColor White
Write-Host "  |    curl -X POST $apiUrl/fields \`                     |" -ForegroundColor White
Write-Host "  |      -H 'Content-Type: application/json' \`             |" -ForegroundColor White
Write-Host "  |      -d '{\"project_id\":\"test\",\"rule\":\"test rule\"}'" -ForegroundColor White
Write-Host "  |                                                         |" -ForegroundColor White
Write-Host "  | 5. Open DQC Studio: http://<ALB_DNS>                    |" -ForegroundColor White
Write-Host "  +-------------------------------------------------------+" -ForegroundColor White
Write-Host ""
Write-Host "  To destroy: .\deploy.ps1 -Destroy -Confirm" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""