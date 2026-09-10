"""Lambda #7 — Find Implicated Fields

Uses LangChain + Amazon Bedrock (Nova Micro) to identify which fields from the
data dictionary are implicated by a given business rule.

Triggered by events from the API Gateway or other Lambdas.
Stores results in DynamoDB DQC Store table.
"""

import json
import logging
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

from langchain_aws import ChatBedrock
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "eu-west-1")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "eu.amazon.nova-micro-v1:0")
S3_BUCKET = os.environ.get("S3_BUCKET", "")
PROMPTS_PREFIX = os.environ.get("PROMPTS_PREFIX", "prompts")
TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "")

# Initialize clients
bedrock_client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
dynamodb = boto3.resource("dynamodb", region_name=BEDROCK_REGION)
s3_client = boto3.client("s3", region_name=BEDROCK_REGION)


def load_prompt(template_name: str) -> str:
    """Load a prompt template from S3."""
    if S3_BUCKET:
        try:
            resp = s3_client.get_object(
                Bucket=S3_BUCKET,
                Key=f"{PROMPTS_PREFIX}/{template_name}.md",
            )
            return resp["Body"].read().decode("utf-8")
        except ClientError:
            logger.warning("Prompt %s not found in S3, using default", template_name)
    return get_default_prompt()


def get_default_prompt() -> str:
    """Default prompt for field identification."""
    return """\
You are an expert in regulatory data quality (IRB / IFRS 9 / BCBS 239).

Given a business rule and a field dictionary, identify ALL fields implicated
by the rule.

## Business Rule

{rule}

## Field Dictionary Context

{fields_context}

## Instructions

1. Read the rule carefully.
2. For each field the rule mentions or needs, return:
   - The exact field name as it appears in the dictionary.
   - A brief description of why it is relevant to the rule.
3. Return the answer as JSON:

```json
{{
  "fields": [
    {{
      "name": "exact_field_name",
      "reason": "brief explanation of relevance",
      "data_type": "STRING|NUMBER|DATE|BOOLEAN"
    }}
  ],
  "confidence": "HIGH|MEDIUM|LOW",
  "bcbs239_dimensions": ["Consistency", "Validity"]
}}
```

4. BCBS 239 dimensions to consider:
   - **Accuracy**: does the rule verify data correctness?
   - **Completeness**: does the rule verify no data is missing?
   - **Consistency**: does the rule verify data is consistent across tables?
   - **Timeliness**: does the rule verify data is up to date?
   - **Uniqueness**: does the rule verify no duplicates exist?
   - **Validity**: does the rule verify data matches a format/value?
"""


def create_llm():
    """Create the Bedrock LLM client."""
    return ChatBedrock(
        model_id=BEDROCK_MODEL_ID,
        client=bedrock_client,
        model_kwargs={
            "temperature": 0.1,
            "max_tokens": 4096,
        },
    )


def handle_event(event: dict) -> dict:
    """Process a field identification request.

    Expected event structure:
    {
        "project_id": "proj_001",
        "rule": "Genera un DQC que verifique que PD_ESTIMADA no sea negativa.",
        "fields_context": "Tabla: exposiciones\\n- PD_ESTIMADA: NUMBER - Probabilidad de incumplimiento estimada\\n- ...",
        "table_name": "exposiciones",
        "sql_dialect": "postgres"
    }
    """
    project_id = event.get("project_id", "unknown")
    rule = event.get("rule", "")
    fields_context = event.get("fields_context", "")
    table_name = event.get("table_name", "")
    sql_dialect = event.get("sql_dialect", "postgres")

    logger.info("Processing rule for project=%s, table=%s", project_id, table_name)
    logger.info("Rule: %s", rule[:200])

    # Build the prompt
    prompt_template = ChatPromptTemplate.from_template(load_prompt("fields_prompt"))
    llm = create_llm()
    parser = JsonOutputParser(pydantic_object=None)

    chain = prompt_template | llm | parser

    try:
        result = chain.invoke({
            "rule": rule,
            "fields_context": fields_context,
        })

        # Store in DynamoDB
        store_result = {
            "report_id": project_id,
            "report_sort": f"fields_{rule[:50].replace(' ', '_')}",
            "type": "field_identification",
            "rule": rule,
            "table_name": table_name,
            "fields": result.get("fields", []),
            "confidence": result.get("confidence", "LOW"),
            "bcbs239_dimensions": result.get("bcbs239_dimensions", []),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "success",
        }

        if TABLE_NAME:
            table = dynamodb.Table(TABLE_NAME)
            table.put_item(Item=store_result)
            logger.info("Stored field identification in DynamoDB for %s", project_id)

        return {
            "statusCode": 200,
            "body": json.dumps(store_result),
            "project_id": project_id,
            "fields": result.get("fields", []),
            "confidence": result.get("confidence", "LOW"),
            "bcbs239_dimensions": result.get("bcbs239_dimensions", []),
        }

    except Exception as e:
        logger.error("Error during field identification: %s", str(e))

        error_result = {
            "report_id": project_id,
            "report_sort": f"fields_{rule[:50].replace(' ', '_')}",
            "type": "field_identification",
            "rule": rule,
            "table_name": table_name,
            "fields": [],
            "confidence": "LOW",
            "error": str(e),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "error",
        }

        if TABLE_NAME:
            table = dynamodb.Table(TABLE_NAME)
            table.put_item(Item=error_result)

        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e), "details": error_result}),
        }


def handler(event: dict, context) -> dict:
    """Lambda entry point."""
    logger.info("Lambda invoked. Event keys: %s", list(event.keys()) if isinstance(event, dict) else type(event))

    if isinstance(event, dict):
        # Check if this is an API Gateway event
        if "httpMethod" in event or "requestContext" in event:
            body = event.get("body", "{}")
            if isinstance(body, str):
                body = json.loads(body)
            event = body

    return handle_event(event)