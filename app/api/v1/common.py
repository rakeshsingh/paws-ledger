"""Shared service instances and utilities used across API route modules."""

import os
import sys
from itsdangerous import URLSafeSerializer
from ...services.integrations import AAHAClient, GoogleAuthService, EmailService, HashService, PDFService

aaha_client = AAHAClient()
google_auth = GoogleAuthService()
email_service = EmailService()
hash_service = HashService()
pdf_service = PDFService()

# Enforce strong secret key in production
_storage_secret = os.getenv("STORAGE_SECRET")
if not _storage_secret and os.getenv("APP_ENV") == "prod":
    print("FATAL: STORAGE_SECRET environment variable is required in production.", file=sys.stderr)
    sys.exit(1)
_storage_secret = _storage_secret or "paws_dev_secret_not_for_production"

serializer = URLSafeSerializer(_storage_secret)

IS_PRODUCTION = os.getenv("APP_ENV") == "prod"
