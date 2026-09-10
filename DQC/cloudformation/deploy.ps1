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
    .\deploy.ps1 -Region us-east-1 -StackName my-dqc -VpcId vpc-xxxx
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
    [string] $SubnetIds = ""
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

function Find-Zip {
    # Try to find a zip executable (Git Bash ships with it on Windows)
    $candidates = @("zip", "C:\Program Files\Git\usr\bin\zip.exe",
                     "C:\Program Files\7-Zip\7z.exe")
    foreach ($c in $candidates) {
        if (Test-Path $c) { return $c }
    }
    Write-Host "`nERROR: 'zip' not found. Install it via:" -ForegroundColor Red
    Write-Host "  - Git Bash ships zip at: C:\Program Files\Git\usr\bin\zip.exe" -ForegroundColor Yellow
    Write-Host "  - Or install 7-Zip and use '7z a'" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Alternatively, build layers manually:" -ForegroundColor Yellow
    Write-Host "  pip install -r requirements.txt -t .\python\" -ForegroundColor Yellow
    Write-Host "  zip -r layer.zip python\\" -ForegroundColor Yellow
    throw "zip not found"
}

$zip = Find-Zip

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

# ── VPC detection ─────────────────────────────────────────────────────
if (-not $Destroy) {
    Write-Step "Detecting VPC and subnets..."

    if (-not $VpcId) {
        try {
            $VpcId = aws ec2 describe-vpcs `
                --region $Region `
                --filters "Name=isDefault,Values=true" `
                --query 'Vpcs[0].VpcId' --output text 2>$null
        } catch { $VpcId = "" }

        if (-not $VpcId -or $VpcId -eq "None") {
            Write-Host "    No default VPC found. Attempting to create one..."
            try {
                $VpcId = aws ec2 create-default-vpc --query 'Vpc.VpcId' --output text --region $Region 2>$null
            } catch { $VpcId = "" }
            if (-not $VpcId -or $VpcId -eq "None") {
                Write-Host "ERROR: Could not create default VPC. Provide VPC and subnet IDs manually:" -ForegroundColor Red
                Write-Host "  .\deploy.ps1 -VpcId vpc-xxx -SubnetIds subnet-xxx,subnet-yyy" -ForegroundColor Red
                exit 1
            }
            Write-Host "    Created VPC: $($VpcId)"
        }
    }

    # Get subnets in the VPC
    try {
        $subnetOutput = aws ec2 describe-subnets `
            --region $Region `
            --filters "Name=vpc-id,Values=$VpcId" `
            --query 'Subnets[*].SubnetId' --output text 2>$null
        $subnets = $subnetOutput -replace "`t", "," -split "," | Where-Object { $_ -and $_ -ne "None" }
    } catch { $subnets = @() }

    if ($subnets.Count -eq 0) {
        Write-Host "ERROR: No subnets found in VPC $($VpcId)" -ForegroundColor Red
        exit 1
    }

    $SubnetIds = ($subnets -join ",")
    Write-Host "    VPC:     $($VpcId)"
    Write-Host "    Subnets: $($SubnetIds)"
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
Write-Step "Building Lambda layer (LangChain + Bedrock)..."

$layerDir = Join-Path $PSScriptDir "lambda-layers\langchain-layer"
if (-not (Test-Path $layerDir)) {
    Write-Host "ERROR: Directory not found: $layerDir" -ForegroundColor Red
    exit 1
}

# Create a temp venv in the layer dir (Windows doesn't have /tmp)
$venvPath = Join-Path $layerDir ".layer-venv"
python -m venv $venvPath 2>$null

# Install dependencies into python/ subdirectory
$targetPath = Join-Path $layerDir "python"
& $venvPath\Scripts\pip install -r (Join-Path $layerDir "requirements.txt") -t $targetPath 2>$null

if (Test-Path $venvPath) { Remove-Item $venvPath -Recurse -Force }

# Build ZIP
if (Test-Path (Join-Path $layerDir "layer.zip")) {
    Remove-Item (Join-Path $layerDir "layer.zip") -Force
}

# Use zip command (Git Bash)
if ($zip -match "7z") {
    & $zip a (Join-Path $layerDir "layer.zip") (Join-Path $layerDir "python") -r 2>$null
} else {
    # Git Bash zip: need to zip from the directory containing python/
    Push-Location $layerDir
    & $zip -r layer.zip python 2>$null
    Pop-Location
}
Write-Host "    Layer ZIP created: layer.zip"

# ── Stage 0b: Package Lambda functions ─────────────────────────────────
$funcDirs = @("find-fields", "sql-generator", "bcbs-classifier")

foreach ($funcDir in $funcDirs) {
    Write-Step "Packaging Lambda: $funcDir..."
    $funcPath = Join-Path $PSScriptDir "lambda-functions" $funcDir
    if (-not (Test-Path $funcPath)) {
        Write-Host "    WARNING: Directory not found: $funcPath — skipping." -ForegroundColor Yellow
        continue
    }

    # Package requirements if present
    if (Test-Path (Join-Path $funcPath "requirements.txt")) {
        $venvPath = Join-Path $funcPath ".lambda-venv"
        python -m venv $venvPath 2>$null
        $targetPath = Join-Path $funcPath "package"
        & $venvPath\Scripts\pip install -r (Join-Path $funcPath "requirements.txt") -t $targetPath 2>$null

        if (Test-Path $venvPath) { Remove-Item $venvPath -Recurse -Force }

        if (Test-Path (Join-Path $funcPath "package.zip")) {
            Remove-Item (Join-Path $funcPath "package.zip") -Force
        }

        Push-Location $funcPath
        & $zip -r package.zip . -x *.pyc -x __pycache__\\* -x *.zip 2>$null
        Pop-Location
    }

    Write-Host "    $funcDir packaged."
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
        "VpcId=$VpcId",
        "SubnetIds=$SubnetIds",
        "BedrockModelId=eu.amazon.nova-micro-v1:0",
        "CPUC_units=1024",
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

$slTemplate = Join-Path $PSScriptDir "dqc-serverless.yaml"
$slArgs = @(
    "cloudformation", "deploy",
    "--stack-name", "$StackName-serverless",
    "--template-file", "`"$slTemplate`"",
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

$s3Bucket = "$StackName-data-$account"
Write-Host "    S3 bucket: $s3Bucket"

aws s3 mb "s3://$s3Bucket" --region $Region 2>$null

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