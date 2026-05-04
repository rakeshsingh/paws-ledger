"""Shared service instances and utilities used across API route modules."""

import os
from itsdangerous import URLSafeSerializer
from ...services.integrations import AAHAClient, GoogleAuthService, EmailService, HashService, PDFService

aaha_client = AAHAClient()
google_auth = GoogleAuthService()
email_service = EmailService()
hash_service = HashService()
pdf_service = PDFService()
serializer = URLSafeSerializer(os.getenv("STORAGE_SECRET", "paws_secret_key"))
