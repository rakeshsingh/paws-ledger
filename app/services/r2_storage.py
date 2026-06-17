"""Cloudflare R2 storage service for vaccination documents and pet photos."""

import os
import logging
import boto3
from botocore.config import Config
from typing import Optional

logger = logging.getLogger("pawsledger.r2")

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "pawsledger-files")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "")



def _get_r2_client():
    """Create a boto3 S3 client configured for Cloudflare R2."""
    client_kwargs = {
        "endpoint_url": f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        "aws_access_key_id": R2_ACCESS_KEY_ID,
        "aws_secret_access_key": R2_SECRET_ACCESS_KEY,
        "config": Config(signature_version="s3v4", region_name="auto"),
    }
    return boto3.client("s3", **client_kwargs)


class R2StorageService:
    """Handles file uploads and downloads from Cloudflare R2."""

    @staticmethod
    def upload_file(
        file_content: bytes,
        key: str,
        content_type: str = "application/octet-stream",
    ) -> Optional[str]:
        """Upload a file to R2 and return the public URL.

        Args:
            file_content: Raw bytes of the file.
            key: Object key (path) in the bucket, e.g. "vaccinations/{pet_id}/{filename}".
            content_type: MIME type of the file.

        Returns:
            Public URL of the uploaded file, or None on failure.
        """
        if not R2_ACCOUNT_ID or not R2_ACCESS_KEY_ID:
            logger.error("R2 not configured — upload cannot proceed (key: %s)", key)
            return None

        try:
            client = _get_r2_client()
            client.put_object(
                Bucket=R2_BUCKET_NAME,
                Key=key,
                Body=file_content,
                ContentType=content_type,
            )
            url = f"{R2_PUBLIC_URL}/{key}" if R2_PUBLIC_URL else f"https://{R2_BUCKET_NAME}.r2.dev/{key}"
            logger.info("File uploaded to R2: %s", key)
            return url
        except Exception as e:
            logger.error("R2 upload failed for key %s: %s", key, e)
            return None

    @staticmethod
    def upload_vaccination_doc(
        pet_id: str,
        filename: str,
        file_content: bytes,
        content_type: str = "application/pdf",
    ) -> Optional[str]:
        """Upload a vaccination document for a pet."""
        key = f"vaccinations/{pet_id}/{filename}"
        return R2StorageService.upload_file(file_content, key, content_type)

    @staticmethod
    def upload_pet_photo(
        pet_id: str,
        filename: str,
        file_content: bytes,
        content_type: str = "image/jpeg",
    ) -> Optional[str]:
        """Upload a pet profile photo."""
        key = f"photos/{pet_id}/{filename}"
        return R2StorageService.upload_file(file_content, key, content_type)

    @staticmethod
    def delete_file(key: str) -> bool:
        """Delete a file from R2."""
        if not R2_ACCOUNT_ID or not R2_ACCESS_KEY_ID:
            logger.warning("R2 not configured — delete skipped (key: %s)", key)
            return False

        try:
            client = _get_r2_client()
            client.delete_object(Bucket=R2_BUCKET_NAME, Key=key)
            logger.info("File deleted from R2: %s", key)
            return True
        except Exception as e:
            logger.error("R2 delete failed for key %s: %s", key, e)
            return False

    @staticmethod
    def generate_presigned_url(key: str, expires_in: int = 3600) -> Optional[str]:
        """Generate a presigned URL for temporary access to a private file."""
        if not R2_ACCOUNT_ID or not R2_ACCESS_KEY_ID:
            return None

        try:
            client = _get_r2_client()
            url = client.generate_presigned_url(
                "get_object",
                Params={"Bucket": R2_BUCKET_NAME, "Key": key},
                ExpiresIn=expires_in,
            )
            return url
        except Exception as e:
            logger.error("R2 presigned URL generation failed: %s", e)
            return None

    @staticmethod
    def backup_database(db_path: str) -> Optional[str]:
        """Backup the SQLite database to R2 with a timestamped key.

        Uses SQLite's backup API (via a file copy of the WAL-checkpointed DB)
        to ensure a consistent snapshot.

        Returns the R2 object key on success, or None on failure.
        """
        import shutil
        import tempfile
        import sqlite3
        from datetime import datetime, timezone

        if not R2_ACCOUNT_ID or not R2_ACCESS_KEY_ID:
            logger.error("R2 not configured — database backup cannot proceed")
            return None

        if not os.path.exists(db_path):
            logger.error("Database file not found: %s", db_path)
            return None

        try:
            # Create a consistent snapshot using SQLite's online backup API
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
                tmp_path = tmp.name

            src = sqlite3.connect(db_path)
            dst = sqlite3.connect(tmp_path)
            src.backup(dst)
            src.close()
            dst.close()

            # Read the snapshot
            with open(tmp_path, "rb") as f:
                content = f.read()

            # Upload with timestamp
            now = datetime.now(timezone.utc)
            date_key = now.strftime("%Y/%m/%d")
            timestamp = now.strftime("%H%M%S")
            key = f"backups/{date_key}/pawsledger-{timestamp}.db"

            url = R2StorageService.upload_file(content, key, "application/x-sqlite3")

            # Cleanup temp file
            os.unlink(tmp_path)

            if url:
                logger.info("Database backup uploaded: %s (%d bytes)", key, len(content))
                return key
            return None

        except Exception as e:
            logger.error("Database backup failed: %s", e)
            return None

    @staticmethod
    def prune_old_backups(keep_days: int = 30) -> int:
        """Delete backup files older than keep_days. Returns count of deleted objects."""
        if not R2_ACCOUNT_ID or not R2_ACCESS_KEY_ID:
            return 0

        from datetime import datetime, timezone, timedelta

        try:
            client = _get_r2_client()
            cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
            deleted = 0

            paginator = client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=R2_BUCKET_NAME, Prefix="backups/"):
                for obj in page.get("Contents", []):
                    if obj["LastModified"].replace(tzinfo=timezone.utc) < cutoff:
                        client.delete_object(Bucket=R2_BUCKET_NAME, Key=obj["Key"])
                        deleted += 1

            if deleted:
                logger.info("Pruned %d old backups (older than %d days)", deleted, keep_days)
            return deleted

        except Exception as e:
            logger.error("Backup pruning failed: %s", e)
            return 0
