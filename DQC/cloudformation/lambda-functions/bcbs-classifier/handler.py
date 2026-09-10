"""Lambda — BCBS 239 DQC Classification

Classifies each DQC check according to the BCBS 239 data quality dimensions:
- Accuracy
- Completeness
- Consistency
- Timeliness
- Uniqueness
- Validity

This is attached to every DQC stored in DynamoDB.
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
TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "")

bedrock_client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
dynamodb = boto3.resource("dynamodb", region_name=BEDROCK_REGION)

BCBS239_DIMENSIONS = {
    "accuracy": {
        "name": "Accuracy",
        "description": "Degree to which data values are correct, reliable, and free from error",
        "examples": ["Negative PD values", "PD > 1.0", "Mismatched amounts"],
    },
    "completeness": {
        "name": "Completeness",
        "description": "Degree to which all required data is present",
        "examples": ["Null client IDs", "Missing maturity dates", "Empty exposure values"],
    },
    "consistency": {
        "name": "Consistency",
        "description": "Degree to which data is coherent and non-contradictory across tables",
        "examples": ["PD_ESTIMADA vs PD_REAL mismatch", "Sector mismatch across tables"],
    },
    "timeliness": {
        "name": "Timeliness",
        "description": "Degree to which data is available and current when needed",
        "examples": ["Outdated maturity dates", "Stale PD estimates"],
    },
    "uniqueness": {
        "name": "Uniqueness",
        "description": "Degree to which each entity is represented only once",
        "examples": ["Duplicate client-product pairs", "Multiple records same PK"],
    },
    "validity": {
        "name": "Validity",
        "description": "Degree to which data conforms to defined formats, values, and business rules",
        "examples": ["Invalid sector codes", "Negative dates", "Out-of-range values"],
    },
}

PROMPT_TEMPLATE = """\
You are a regulatory data quality expert. Classify this DQC check according
to BCBS 239 data quality dimensions.

## DQC Rule

{rule}

## DQC SQL

{sql}

## DQC Fields

{fields_json}

## Instructions

BCBS 239 data quality dimensions:
{dimension_descriptions}

For each dimension, determine if it applies to this DQC check.
Return JSON:

```json
{{
  "applicable_dimensions": ["Consistency", "Validity"],
  "dimension_scores": {{
    "accuracy": 0.0,
    "completeness": 0.0,
    "consistency": 0.9,
    "timeliness": 0.0,
    "uniqueness": 0.0,
    "validity": 0.8
  }},
  "primary_dimension": "Consistency",
  "explanation": "Primary: Consistency — this check compares PD_ESTIMADA with PD_REAL..."
}}
```

Scores should be between 0.0 and 1.0 indicating the relevance of each dimension.
"""


def handler(event: dict, context) -> dict:
    """Process BCBS 239 classification.

    Can be invoked:
    1. As a standalone Lambda with rule/fields/SQL in the event body
    2. As a DynamoDB stream trigger (event contains the DQC item)
    """
    logger.info("BCBS Classifier Lambda invoked")

    # Handle DynamoDB stream event vs direct API call
    rule = ""
    sql = ""
    fields = []

    if "Records" in event:
        # DynamoDB stream trigger
        record = event["Records"][0]
        dynamodb_record = record.get("dynamodb", {})
        item = dynamodb_record.get("newImage", {})

        # Convert DynamoDB types to Python
        def parse_item(img):
            result = {}
            for k, v in img.items():
                for type_key, value in v.items():
                    result[k] = value
            return result

        item = parse_item(item)
        rule = item.get("rule", "")
        sql = item.get("sql", "")
        fields = item.get("fields", [])
        project_id = item.get("report_id", "")
    else:
        # Direct Lambda call
        body = event
        if "body" in event:
            body_str = event["body"]
            if isinstance(body_str, str):
                body = json.loads(body_str)

        rule = body.get("rule", "")
        sql = body.get("sql", "")
        fields = body.get("fields", [])
        project_id = body.get("project_id", "")

    if not rule:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "No rule provided"}),
        }

    # Build dimension descriptions
    dim_desc = "\n".join(
        f"- **{info['name']}**: {info['description']} (examples: {', '.join(info['examples'])})"
        for info in BCBS239_DIMENSIONS.values()
    )

    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    llm = ChatBedrock(
        model_id=BEDROCK_MODEL_ID,
        client=bedrock_client,
        model_kwargs={"temperature": 0.0, "max_tokens": 1024},
    )
    parser = JsonOutputParser()

    chain = prompt_template | llm | parser

    try:
        result = chain.invoke({
            "rule": rule,
            "sql": sql or "(not yet generated)",
            "fields_json": json.dumps(fields, ensure_ascii=False, indent=2),
            "dimension_descriptions": dim_desc,
        })

        classification = {
            "applicable_dimensions": result.get("applicable_dimensions", []),
            "dimension_scores": result.get("dimension_scores", {}),
            "primary_dimension": result.get("primary_dimension", "Consistency"),
            "explanation": result.get("explanation", ""),
        }

        logger.info("BCBS classification: %s", json.dumps(classification))

        # Update DynamoDB with classification
        if TABLE_NAME and project_id:
            table = dynamodb.Table(TABLE_NAME)
            table.update_item(
                Key={
                    "report_id": project_id,
                    "report_sort": f"dqc_{rule[:30].replace(' ', '_')}",
                },
                UpdateExpression="SET bcbs239_dimensions = :dims, primary_bcbs_dimension = :primary, bcbs_explanation = :expl",
                ExpressionAttributeValues={
                    ":dims": classification["applicable_dimensions"],
                    ":primary": classification["primary_dimension"],
                    ":expl": classification["explanation"],
                },
            )

        return {
            "statusCode": 200,
            "body": json.dumps(classification),
            "classification": classification,
        }

    except Exception as e:
        logger.error("BCBS classification failed: %s", str(e))
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }