import io
import json
import os
import time
import zlib
from datetime import datetime

import boto3

AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
TIMEOUT_SECONDS = int(os.environ.get("E2E_TIMEOUT_SECONDS", "90"))

session = boto3.Session(
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
    region_name=AWS_REGION,
)

s3_client = session.client("s3", endpoint_url=AWS_ENDPOINT_URL)
ddb_resource = session.resource("dynamodb", endpoint_url=AWS_ENDPOINT_URL)


def build_test_image_bytes() -> bytes:
    # Build a tiny valid PNG without external dependencies.
    width, height = 2, 2
    raw = b""
    for _ in range(height):
        raw += b"\x00" + b"\x20\x5a\x96" * width

    compressor = zlib.compressobj()
    compressed = compressor.compress(raw) + compressor.flush()

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            len(data).to_bytes(4, "big")
            + tag
            + data
            + zlib.crc32(tag + data).to_bytes(4, "big")
        )

    png = io.BytesIO()
    png.write(b"\x89PNG\r\n\x1a\n")
    png.write(chunk(b"IHDR", width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00"))
    png.write(chunk(b"IDAT", compressed))
    png.write(chunk(b"IEND", b""))
    return png.getvalue()


def wait_for_processed_object(key: str) -> None:
    processed_bucket = os.environ["PROCESSED_BUCKET"]
    deadline = time.time() + TIMEOUT_SECONDS
    while time.time() < deadline:
        try:
            s3_client.head_object(Bucket=processed_bucket, Key=key)
            return
        except Exception:
            time.sleep(2)
    raise TimeoutError(f"Processed image {key} not found in {processed_bucket} within timeout")


def wait_for_metadata(original_key: str) -> dict:
    ddb_table = os.environ.get("DDB_TABLE", "ImageMetadataTable")
    table = ddb_resource.Table(ddb_table)
    deadline = time.time() + TIMEOUT_SECONDS
    while time.time() < deadline:
        response = table.get_item(Key={"originalKey": original_key})
        item = response.get("Item")
        if item:
            return item
        time.sleep(2)
    raise TimeoutError(f"Metadata for {original_key} not found in {ddb_table} within timeout")


def main() -> None:
    input_bucket = os.environ["INPUT_BUCKET"]
    original_key = f"e2e-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.png"
    processed_key = f"resized_{original_key}"

    print(f"Uploading test image to {input_bucket}/{original_key}")
    s3_client.put_object(Bucket=input_bucket, Key=original_key, Body=build_test_image_bytes(), ContentType="image/png")

    print(f"Waiting for processed image {processed_key}")
    wait_for_processed_object(processed_key)

    print("Waiting for DynamoDB metadata entry")
    item = wait_for_metadata(original_key)

    assert item["processedKey"] == processed_key
    assert item["status"] == "SUCCESS"

    print("E2E success")
    print(json.dumps(item, indent=2, default=str))


if __name__ == "__main__":
    main()
