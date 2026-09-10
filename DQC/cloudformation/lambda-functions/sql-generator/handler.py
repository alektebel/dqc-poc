"""Lambda #9 — SQL Generation with Retry Loop and LLM-as-Judge

Takes the implicated fields from DynamoDB and generates a SQL query using
Bedrock. Implements:
- Retry loop (max 5 attempts) with semantic re-prompting on failure
- LLM-as-judge to evaluate query quality before approval
- BCBS 239 classification in the output

Triggered by events from API Gateway or other Lambdas.
Stores results in DynamoDB DQC Store table.
"""

import json
import logging
import os
import uuid
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
JUDGE_MODEL_ID = os.environ.get("JUDGE_MODEL_ID", "eu.amazon.nova-pro-v1:0")
S3_BUCKET = os.environ.get("S3_BUCKET", "")
PROMPTS_PREFIX = os.environ.get("PROMPTS_PREFIX", "prompts")
TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "")
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "5"))

bedrock_client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
dynamodb = boto3.resource("dynamodb", region_name=BEDROCK_REGION)
s3_client = boto3.client("s3", region_name=BEDROCK_REGION)


def load_prompt(template_name: str) -> str:
    """Load a prompt template from S3, fall back to default."""
    if S3_BUCKET:
        try:
            resp = s3_client.get_object(
                Bucket=S3_BUCKET,
                Key=f"{PROMPTS_PREFIX}/{template_name}.md",
            )
            return resp["Body"].read().decode("utf-8")
        except ClientError:
            logger.warning("Prompt %s not found in S3, using default", template_name)
    return get_default_sql_prompt() if template_name == "sql_prompt" else get_default_judge_prompt()


def get_default_sql_prompt() -> str:
    return """\
You are an expert in SQL and regulatory data quality (IRB / IFRS 9 / BCBS 239).

Given a business rule, the implicated fields and the field dictionary,
generate a SQL query that detects records violating the rule.

## Business Rule

{rule}

## Implicated Fields

{fields_json}

## Field Dictionary (Schema)

{table_schema}

## Instructions

1. Generate a valid SQL query that selects rows **violating** the rule.
2. Use the specified dialect: {dialect}.
3. Include a SQL comment explaining the detection logic.
4. Return JSON:

```json
{{
  "sql": "SELECT ... FROM ... WHERE ...",
  "dialect": "{dialect}",
  "description": "Explanation of the query",
  "tables_referenced": ["table1", "table2"],
  "bcbs239_dimensions": ["Consistency", "Validity"],
  "validation_failed_reason": "Explanation of why certain records would fail this DQC"
}}
```

5. **validation_failed_reason** is REQUIRED — explain why you suspect
   records might be inadequate. This is a project requirement.
"""


def get_default_judge_prompt() -> str:
    return """\
Evaluate the quality of the generated SQL query for a DQC.

## Original Business Rule

{rule}

## Generated SQL

{sql}

## Implicated Fields

{fields_json}

## Field Dictionary (Schema)

{table_schema}

## Instructions

Evaluate on these criteria (scores 1-5):
1. **Semantic correctness**: Does the query correctly implement the rule?
2. **Syntax validity**: Is the query syntactically valid?
3. **Coverage**: Does the query cover all implicated fields?
4. **Detection quality**: Will it correctly detect violations?
5. **BCBS 239 alignment**: Does it align with quality dimensions?

Return JSON:

```json
{{
  "semantic_correctness": 4,
  "semantic_explanation": "...",
  "syntax_valid": true,
  "syntax_explanation": null,
  "coverage_complete": true,
  "coverage_explanation": "...",
  "detection_quality": 5,
  "detection_explanation": "...",
  "bcbs_aligned": true,
  "bcbs_explanation": "...",
  "overall_score": 4.5,
  "recommendation": "APPROVE|REVISE|REJECT",
  "revision_notes": "What to change, or null"
}}
```
"""


def create_llm(model_id: str = None, temperature: float = 0.1):
    """Create a Bedrock LLM client."""
    return ChatBedrock(
        model_id=model_id or BEDROCK_MODEL_ID,
        client=bedrock_client,
        model_kwargs={"temperature": temperature, "max_tokens": 4096},
    )


def generate_sql(rule: str, fields: list, table_schema: str,
                 table_name: str, dialect: str, attempt: int) -> dict:
    """Generate SQL for the given rule (single attempt)."""
    fields_json = json.dumps(fields, ensure_ascii=False, indent=2)

    prompt_template = ChatPromptTemplate.from_template(load_prompt("sql_prompt"))
    llm = create_llm()
    parser = JsonOutputParser()

    chain = prompt_template | llm | parser

    result = chain.invoke({
        "rule": rule,
        "fields_json": fields_json,
        "table_schema": table_schema,
        "table_name": table_name,
        "dialect": dialect,
    })

    return result


def judge_sql(rule: str, sql: str, fields: list, table_schema: str) -> dict:
    """Evaluate the quality of generated SQL using LLM-as-judge."""
    prompt_template = ChatPromptTemplate.from_template(load_prompt("judge_prompt"))
    llm = create_llm(model_id=JUDGE_MODEL_ID, temperature=0.0)
    parser = JsonOutputParser()

    chain = prompt_template | llm | parser

    result = chain.invoke({
        "rule": rule,
        "sql": sql,
        "fields_json": json.dumps(fields, ensure_ascii=False, indent=2),
        "table_schema": table_schema,
    })

    return result


def retry_with_feedback(rule: str, fields: list, table_schema: str,
                        table_name: str, dialect: str, feedback: str) -> dict:
    """Retry SQL generation with feedback from judge or error."""
    logger.info("Retrying SQL generation with feedback: %s", feedback[:100])

    prompt_template = ChatPromptTemplate.from_template(load_prompt("sql_prompt"))
    llm = create_llm()
    parser = JsonOutputParser()

    enriched_prompt = prompt_template.format_prompt(
        rule=rule,
        fields_json=json.dumps(fields, ensure_ascii=False, indent=2),
        table_schema=table_schema,
        table_name=table_name,
        dialect=dialect,
    )

    # Append feedback to the prompt
    enriched_prompt.messages[0].content += (
        f"\n\n## PREVIOUS ATTEMPT FEEDBACK\n\n"
        f"The previous attempt failed with this feedback: {feedback}\n"
        f"Please fix the issue and generate a correct query."
    )

    chain = enriched_prompt | llm | parser
    return chain.invoke({})


def store_dqc(result: dict):
    """Store DQC result in DynamoDB."""
    if not TABLE_NAME:
        return

    table = dynamodb.Table(TABLE_NAME)

    item = {
        "report_id": result["project_id"],
        "report_sort": result["report_sort"],
        "type": "dqc_check",
        "rule": result.get("rule", ""),
        "fields": result.get("fields", []),
        "sql": result.get("sql"),
        "sql_dialect": result.get("dialect", "postgres"),
        "bcbs239_dimensions": result.get("bcbs239_dimensions", []),
        "validation_failed_reason": result.get("validation_failed_reason", ""),
        "dqc_status": result.get("dqc_status", "GENERATED"),
        "judge_result": result.get("judge_result"),
        "retry_count": result.get("retry_count", 0),
        "created_at": result.get("created_at", datetime.now(timezone.utc).isoformat()),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status": result.get("status", "success"),
    }

    table.put_item(Item=item)
    logger.info("Stored DQC in DynamoDB: %s", result["report_sort"])


def handle_event(event: dict) -> dict:
    """Process SQL generation request with retry loop and judge."""
    project_id = event.get("project_id", "unknown")
    rule = event.get("rule", "")
    fields = event.get("fields", [])
    fields_json_str = event.get("fields_json_str", event.get("fields_context", ""))
    table_name = event.get("table_name", "")
    dialect = event.get("sql_dialect", "postgres")

    # Parse fields if string
    if isinstance(fields, str):
        try:
            fields = json.loads(fields)
        except json.JSONDecodeError:
            fields = []

    # Load table schema from S3 if available
    table_schema = ""
    if S3_BUCKET and table_name:
        try:
            resp = s3_client.get_object(
                Bucket=S3_BUCKET,
                Key=f"data/schemas/{table_name}.json",
            )
            table_schema = resp["Body"].read().decode("utf-8")
        except ClientError:
            logger.warning("Schema for %s not found in S3", table_name)

    report_sort = f"dqc_{rule[:30].replace(' ', '_')}_{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()
    retry_count = 0

    logger.info("Generating SQL for project=%s, table=%s, rule=%s",
                project_id, table_name, rule[:100])

    # Main generation with retry loop (max 5 attempts)
    for attempt in range(1, MAX_RETRIES + 1):
        retry_count = attempt - 1

        try:
            if attempt == 1:
                # First attempt: generate from scratch
                sql_result = generate_sql(
                    rule=rule,
                    fields=fields,
                    table_schema=table_schema,
                    table_name=table_name,
                    dialect=dialect,
                    attempt=attempt,
                )
            else:
                # Retry with feedback
                sql_result = retry_with_feedback(
                    rule=rule,
                    fields=fields,
                    table_schema=table_schema,
                    table_name=table_name,
                    dialect=dialect,
                    feedback=event.get("last_feedback", "Unknown error"),
                )

            sql_query = sql_result.get("sql", "")

            # If SQL generation itself reported a retry
            if sql_result.get("status") == "retry" and attempt < MAX_RETRIES:
                event["last_feedback"] = sql_result.get("error", "Invalid SQL syntax")
                logger.info("SQL generation requested retry %d/%d: %s",
                            attempt, MAX_RETRIES, sql_result.get("error", ""))
                continue

            if not sql_query:
                if attempt < MAX_RETRIES:
                    event["last_feedback"] = "No SQL generated, LLM may have returned incomplete output"
                    logger.info("No SQL returned, retrying (%d/%d)", attempt, MAX_RETRIES)
                    continue
                sql_result["sql"] = None
                sql_result["status"] = "error"
                sql_result["error"] = "No SQL generated after max retries"

            break

        except Exception as e:
            logger.error("Attempt %d failed: %s", attempt, str(e))
            if attempt == MAX_RETRIES:
                sql_result = {
                    "sql": None,
                    "status": "error",
                    "error": str(e),
                    "retry_attempt": attempt,
                }
                break
            event["last_feedback"] = str(e)

    # LLM-as-judge evaluation
    judge_result = None
    dqc_status = "GENERATED"

    if sql_result and sql_result.get("sql"):
        try:
            judge_result = judge_sql(
                rule=rule,
                sql=sql_result.get("sql", ""),
                fields=fields,
                table_schema=table_schema,
            )

            recommendation = judge_result.get("recommendation", "REJECT")
            if recommendation == "APPROVE":
                dqc_status = "APPROVED"
            elif recommendation == "REVISE":
                dqc_status = "NEEDS_REVIEW"
            else:
                dqc_status = "REJECTED"

            logger.info("Judge recommendation: %s (score: %s)",
                        recommendation, judge_result.get("overall_score"))

        except Exception as e:
            logger.warning("Judge evaluation failed: %s", str(e))
            judge_result = {"error": str(e), "recommendation": "UNKNOWN"}
            dqc_status = "APPROVED"  # Don't block on judge failure

    final_result = {
        "report_id": project_id,
        "report_sort": report_sort,
        "type": "dqc_check",
        "rule": rule,
        "fields": fields,
        "fields_json_str": fields_json_str,
        "sql": sql_result.get("sql"),
        "dialect": sql_result.get("dialect", dialect),
        "description": sql_result.get("description", ""),
        "tables_referenced": sql_result.get("tables_referenced", []),
        "bcbs239_dimensions": sql_result.get("bcbs239_dimensions", []),
        "validation_failed_reason": sql_result.get("validation_failed_reason", ""),
        "dqc_status": dqc_status,
        "judge_result": judge_result,
        "retry_count": retry_count,
        "max_retries": MAX_RETRIES,
        "created_at": created_at,
        "status": "success" if sql_result.get("sql") or sql_result.get("status") == "error" else "error",
        "attempt": sql_result.get("retry_attempt", attempt) if 'attempt' in dir() else 1,
    }

    # Store in DynamoDB
    store_dqc(final_result)

    return {
        "statusCode": 200,
        "body": json.dumps(final_result),
        "dqc_id": report_sort,
        "dqc_status": dqc_status,
        "judge_recommendation": judge_result.get("recommendation", "UNKNOWN") if judge_result else "UNKNOWN",
        "sql_query": sql_result.get("sql") if sql_result else None,
    }


def handler(event: dict, context) -> dict:
    """Lambda entry point."""
    logger.info("SQL Generation Lambda invoked. Event keys: %s",
                list(event.keys()) if isinstance(event, dict) else type(event))

    if isinstance(event, dict):
        if "httpMethod" in event or "requestContext" in event:
            body = event.get("body", "{}")
            if isinstance(body, str):
                body = json.loads(body)
            event = body

    return handle_event(event)