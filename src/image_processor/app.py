import io
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Dict, Tuple

import boto3
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client("s3")
sqs_client = boto3.client("sqs")

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_supported_image(key: str) -> bool:
    lowered = key.lower()
    return any(lowered.endswith(ext) for ext in ALLOWED_EXTENSIONS)


def process_image(image_bytes: bytes, target_width: int, watermark_text: str) -> Tuple[bytes, Dict[str, int], Dict[str, int], str]:
    try:
        image = Image.open(io.BytesIO(image_bytes))
    except UnidentifiedImageError as exc:
        raise ValueError("Unsupported or corrupted image file") from exc

    image_format = (image.format or "PNG").upper()
    if image_format == "JPG":
        image_format = "JPEG"

    original_size = {"width": image.width, "height": image.height}

    ratio = target_width / float(image.width)
    new_height = max(1, int(image.height * ratio))
    resized = image.resize((target_width, new_height))

    draw = ImageDraw.Draw(resized)
    font = ImageFont.load_default()
    text_bbox = draw.textbbox((0, 0), watermark_text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    x = max(10, resized.width - text_width - 10)
    y = max(10, resized.height - text_height - 10)

    if resized.mode not in ("RGB", "RGBA"):
        resized = resized.convert("RGBA")
    draw = ImageDraw.Draw(resized)
    draw.rectangle((x - 4, y - 2, x + text_width + 4, y + text_height + 2), fill=(0, 0, 0, 140))
    draw.text((x, y), watermark_text, fill=(255, 255, 255, 255), font=font)

    output = io.BytesIO()
    save_image = resized
    if image_format == "JPEG" and save_image.mode == "RGBA":
        save_image = save_image.convert("RGB")
    save_image.save(output, format=image_format)

    return output.getvalue(), original_size, {"width": target_width, "height": new_height}, image_format


def send_error_to_dlq(original_key: str, exc: Exception) -> None:
    dlq_url = os.environ["DLQ_QUEUE_URL"]
    payload = {
        "originalKey": original_key,
        "errorType": exc.__class__.__name__,
        "errorMessage": str(exc),
        "timestamp": _utc_now_iso(),
    }
    sqs_client.send_message(QueueUrl=dlq_url, MessageBody=json.dumps(payload))


def handler(event, context):
    target_width = int(os.environ.get("TARGET_WIDTH", "200"))
    watermark_text = os.environ.get("WATERMARK_TEXT", "© MyCompany")
    queue_url = os.environ["SQS_QUEUE_URL"]
    processed_bucket = os.environ["PROCESSED_BUCKET_NAME"]

    processed_count = 0
    failed_count = 0

    for record in event.get("Records", []):
        original_key = "unknown"
        started = time.time()

        try:
            s3_info = record["s3"]
            source_bucket = s3_info["bucket"]["name"]
            original_key = s3_info["object"]["key"]

            if not is_supported_image(original_key):
                raise ValueError("Only JPG/JPEG/PNG files are supported")

            response = s3_client.get_object(Bucket=source_bucket, Key=original_key)
            image_bytes = response["Body"].read()

            transformed_bytes, original_size, new_size, image_format = process_image(
                image_bytes=image_bytes,
                target_width=target_width,
                watermark_text=watermark_text,
            )

            processed_key = f"resized_{original_key}"
            content_type = "image/jpeg" if image_format == "JPEG" else "image/png"

            s3_client.put_object(
                Bucket=processed_bucket,
                Key=processed_key,
                Body=transformed_bytes,
                ContentType=content_type,
            )

            duration_ms = int((time.time() - started) * 1000)
            message = {
                "originalKey": original_key,
                "processedKey": processed_key,
                "timestamp": _utc_now_iso(),
                "status": "SUCCESS",
                "processingDetails": {
                    "originalSize": original_size,
                    "newSize": new_size,
                    "durationMs": duration_ms,
                },
            }

            sqs_client.send_message(QueueUrl=queue_url, MessageBody=json.dumps(message))
            processed_count += 1
            logger.info("Image processed successfully: %s", json.dumps(message))

        except Exception as exc:
            failed_count += 1
            logger.exception("Failed to process image %s", original_key)
            send_error_to_dlq(original_key, exc)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "Image processing completed",
                "processed": processed_count,
                "failed": failed_count,
            }
        ),
    }
