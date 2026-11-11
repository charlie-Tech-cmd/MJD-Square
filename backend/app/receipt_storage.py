import logging
from functools import lru_cache
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.config import ROOT_DIR, settings

logger = logging.getLogger(__name__)
LOCAL_RECEIPT_STORAGE_DIR = ROOT_DIR / "backend" / "data" / "payment-receipts"


class ReceiptStorageError(Exception):
    pass


def _storage_backend() -> str:
    s3_settings = (
        settings.s3_region,
        settings.s3_bucket,
        settings.s3_access_key_id,
        settings.s3_secret_access_key,
    )
    if all(s3_settings):
        return "s3"
    if any(s3_settings):
        raise ReceiptStorageError("S3 receipt storage is only partially configured.")
    if settings.app_env == "development":
        return "local"
    raise ReceiptStorageError(
        "Payment receipt storage is not configured. Contact your administrator."
    )


def _storage_settings() -> tuple[str, str, str, str, str]:
    if _storage_backend() != "s3":
        raise ReceiptStorageError("S3 receipt storage is not configured.")
    return (
        settings.s3_region,
        settings.s3_bucket,
        settings.s3_access_key_id,
        settings.s3_secret_access_key,
        settings.s3_endpoint_url or "",
    )


def _local_object_path(object_key: str) -> Path:
    path = Path(*Path(object_key).parts)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ReceiptStorageError("The payment receipt has an invalid storage key.")
    root = LOCAL_RECEIPT_STORAGE_DIR.resolve()
    target = (root / path).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ReceiptStorageError("The payment receipt has an invalid storage key.") from exc
    return target


@lru_cache(maxsize=1)
def _s3_client():
    region, _, access_key, secret_key, endpoint = _storage_settings()
    return boto3.client(
        "s3",
        endpoint_url=endpoint or None,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def store_receipt(object_key: str, content: bytes, content_type: str) -> None:
    if _storage_backend() == "local":
        path = _local_object_path(object_key)
        try:
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with path.open("xb") as descriptor:
                descriptor.write(content)
            path.chmod(0o600)
        except OSError as exc:
            logger.exception("Unable to store payment evidence in local private storage.")
            raise ReceiptStorageError(
                "Unable to save the receipt to local secure storage. Please try again."
            ) from exc
        return

    _, bucket, _, _, _ = _storage_settings()
    try:
        _s3_client().put_object(
            Bucket=bucket,
            Key=object_key,
            Body=content,
            ContentType=content_type,
            ContentDisposition="attachment",
            CacheControl="private, no-store",
        )
    except (BotoCoreError, ClientError) as exc:
        logger.exception("Unable to store payment evidence in object storage.")
        raise ReceiptStorageError(
            "Unable to save the receipt to secure storage. Please try again."
        ) from exc


def remove_receipt(object_key: str) -> None:
    if _storage_backend() == "local":
        try:
            _local_object_path(object_key).unlink()
        except OSError as exc:
            logger.exception("Unable to clean up an unreferenced local payment evidence file.")
            raise ReceiptStorageError(
                "Unable to clean up an unreferenced receipt file."
            ) from exc
        return

    _, bucket, _, _, _ = _storage_settings()
    try:
        _s3_client().delete_object(Bucket=bucket, Key=object_key)
    except (BotoCoreError, ClientError) as exc:
        logger.exception("Unable to clean up an unreferenced payment evidence object.")
        raise ReceiptStorageError("Unable to clean up an unreferenced receipt object.") from exc


def local_receipt_path(object_key: str) -> Path | None:
    if _storage_backend() != "local":
        return None
    path = _local_object_path(object_key)
    if not path.is_file():
        raise ReceiptStorageError("The saved payment receipt could not be found.")
    return path


def receipt_download_url(object_key: str, filename: str, content_type: str) -> str:
    _, bucket, _, _, _ = _storage_settings()
    try:
        return _s3_client().generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": object_key,
                "ResponseContentDisposition": f'attachment; filename="{filename}"',
                "ResponseContentType": content_type,
                "ResponseCacheControl": "private, no-store",
            },
            ExpiresIn=120,
        )
    except (BotoCoreError, ClientError) as exc:
        logger.exception("Unable to create a private payment receipt download URL.")
        raise ReceiptStorageError(
            "Unable to retrieve the saved receipt. Please try again."
        ) from exc
