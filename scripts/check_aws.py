#!/usr/bin/env python
"""Diagnose AWS credential / region / Bedrock problems for the DQC backend.

Run it from whichever environment is failing — the same interpreter that runs
the app, so it sees the same credential chain:

    .venv/bin/python scripts/check_aws.py
    docker exec dqc-poc-api python scripts/check_aws.py

boto3 and the AWS CLI share one credential chain (env vars -> ~/.aws ->
SSO cache -> IMDS), so a venv never changes which credentials are found. When
the CLI and the app disagree, the difference is always in the environment.

Never prints secrets: access key ids are masked and secrets are never read out.
"""
from __future__ import annotations

import os
import sys

REGION = os.getenv("BEDROCK_REGION") or os.getenv("AWS_REGION") or "eu-west-1"
MODEL = os.getenv("BEDROCK_MODEL_ID", "eu.amazon.nova-micro-v1:0")

# Opt-in regions: disabled ones fail with InvalidClientTokenId, which reads
# like a bad credential but is not one.
OPT_IN_PREFIXES = ("eu-south-", "me-", "af-", "ap-east-", "il-", "ap-southeast-3",
                   "ap-southeast-4", "ap-southeast-5", "ap-southeast-7",
                   "ca-west-", "mx-central-")


def mask(v: str | None) -> str:
    if not v:
        return "(unset)"
    return f"{v[:4]}…{v[-4:]}" if len(v) > 8 else "(set)"


def main() -> int:
    print("── environment ──────────────────────────────────────────────")
    print(f"  python            {sys.executable}")
    print(f"  region under test {REGION}")
    print(f"  model             {MODEL}")
    for k in ("AWS_PROFILE", "AWS_REGION", "AWS_DEFAULT_REGION"):
        print(f"  {k:17} {os.getenv(k) or '(unset)'}")
    print(f"  {'AWS_ACCESS_KEY_ID':17} {mask(os.getenv('AWS_ACCESS_KEY_ID'))}")
    print(f"  {'AWS_SECRET_ACCESS_KEY':17} {'(set)' if os.getenv('AWS_SECRET_ACCESS_KEY') else '(unset)'}")
    print(f"  {'AWS_SESSION_TOKEN':17} {'(set)' if os.getenv('AWS_SESSION_TOKEN') else '(unset)'}")

    try:
        import boto3
        import botocore
    except ImportError:
        print("\n✗ boto3 is not installed in THIS interpreter.")
        print("  The app would report llm_backend=stub. Fix: pip install -r requirements.txt")
        return 1
    print(f"\n  boto3             {boto3.__version__}")

    session = boto3.session.Session(region_name=REGION)
    creds = session.get_credentials()
    if creds is None:
        print("\n✗ No credentials found anywhere in the chain.")
        print("  Fix: aws configure   (or aws sso login, or set AWS_ACCESS_KEY_ID/SECRET)")
        return 1

    frozen = creds.get_frozen_credentials()
    print(f"  credential source {creds.method}")
    print(f"  access key id     {mask(frozen.access_key)}")
    print(f"  session token     {'present' if frozen.token else 'none (long-lived key)'}")

    # A permanent AKIA key carrying a session token is the classic
    # InvalidClientTokenId: the token is stale but overrides the good key.
    suspect_stale = bool(frozen.token) and frozen.access_key.startswith("AKIA")
    if suspect_stale:
        print("\n  ! An AKIA… key normally has NO session token. A leftover")
        print("    AWS_SESSION_TOKEN overrides a working key and produces")
        print("    InvalidClientTokenId. Try: unset AWS_SESSION_TOKEN")

    print("\n── identity ─────────────────────────────────────────────────")
    control = "us-east-1"  # always enabled, so it separates region from credential faults
    results = {}
    for region in dict.fromkeys([control, REGION]):
        try:
            ident = session.client("sts", region_name=region).get_caller_identity()
            results[region] = None
            print(f"  ✓ {region:14} {ident['Arn']}")
        except botocore.exceptions.ClientError as exc:
            code = exc.response["Error"]["Code"]
            results[region] = code
            print(f"  ✗ {region:14} {code}: {exc.response['Error']['Message'][:60]}")
        except Exception as exc:  # noqa: BLE001 - report anything, do not crash
            results[region] = type(exc).__name__
            print(f"  ✗ {region:14} {type(exc).__name__}: {str(exc)[:60]}")

    if results.get(control) is None and results.get(REGION) == "InvalidClientTokenId":
        print(f"\n✗ Credentials are VALID but rejected in {REGION}.")
        if REGION.startswith(OPT_IN_PREFIXES):
            print(f"  {REGION} is an opt-in region. Enable it (Console > Account >")
            print("  AWS Regions) or use an enabled one such as eu-west-1.")
        else:
            print("  The region appears not to be enabled for this account.")
        try:
            enabled = session.client("account", region_name=control).list_regions(
                RegionOptStatusContains=["ENABLED", "ENABLED_BY_DEFAULT"])
            names = sorted(r["RegionName"] for r in enabled["Regions"])
            print("  Enabled regions: " + ", ".join(names))
        except Exception:
            print("  (account:ListRegions denied — check the console)")
        return 1

    if results.get(control) == "InvalidClientTokenId":
        print("\n✗ Rejected even in us-east-1, so the credentials really are bad.")
        if suspect_stale:
            print("  Most likely the stale AWS_SESSION_TOKEN noted above.")
        else:
            print("  Temporary credentials expire — re-run 'aws sso login' or refresh them.")
        return 1

    if results.get(REGION) is not None:
        return 1

    print("\n── bedrock ──────────────────────────────────────────────────")
    try:
        client = session.client("bedrock-runtime", region_name=REGION)
        resp = client.converse(
            modelId=MODEL,
            messages=[{"role": "user", "content": [{"text": "Reply with the single word: OK"}]}],
            inferenceConfig={"maxTokens": 10},
        )
        print(f"  ✓ {MODEL} -> {resp['output']['message']['content'][0]['text'].strip()!r}")
        print("\n✓ All good. Start the API with REGLLM_LLM=bedrock (or auto).")
        return 0
    except botocore.exceptions.ClientError as exc:
        code = exc.response["Error"]["Code"]
        print(f"  ✗ {code}: {exc.response['Error']['Message'][:120]}")
        if code == "AccessDeniedException":
            print("\n  Enable model access: Console > Bedrock > Model access > Nova.")
        elif code == "ValidationException" and "on-demand" in str(exc):
            print("\n  Use the inference profile id, e.g. eu.amazon.nova-micro-v1:0,")
            print("  not the bare amazon.nova-micro-v1:0 that list-foundation-models shows.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
