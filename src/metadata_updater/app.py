import json
import logging
import os
from typing import Dict

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ.get("DYNAMODB_TABLE_NAME", "ImageMetadataTable"))


def parse_message_body(body: str) -> Dict:
    payload = json.loads(body)
    required = ["originalKey", "processedKey", "timestamp", "status", "processingDetails"]
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")
    return payload


def persist_metadata(item: Dict) -> None:
    try:
        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(originalKey)",
        )
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code == "ConditionalCheckFailedException":
            logger.info("Duplicate record ignored for key %s", item["originalKey"])
            return
        raise


def handler(event, context):
    processed = 0

    for record in event.get("Records", []):
        payload = parse_message_body(record["body"])
        item = {
            "originalKey": payload["originalKey"],
            "processedKey": payload["processedKey"],
            "timestamp": payload["timestamp"],
            "status": payload["status"],
            "processingDetails": payload["processingDetails"],
        }
        persist_metadata(item)
        processed += 1

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Metadata updated successfully", "processed": processed}),
    }
