# Epic: Free Tier Asymmetric Recovery Messaging
Epic Description: As a PawsLedger platform user, I want a zero-cost, one-way alert channel on the free tier so that authenticated finders can notify pet owners that their pet has been found, without exposing raw personal identifiable information (PII). Both parties must be authenticated via Google OAuth to ensure verified identities and prevent abuse. Bidirectional secure messaging, GPS sharing, and full nudge history are available on the Verified tier (see business_requirements_v1_verified_tier.md).

## US-01: Initiating the Secure Nudge (Finder Vector)

As a Pet Finder who has scanned a lost pet's PawsLedger Smart Tag, I want to submit a secure contact form directly on the public PawsPage, so that I can alert the owner that their pet is safe while preserving both parties' data privacy.

### Acceptance Criteria:
AC 1.1: The public PawsPage must feature a prominent Send Secure Nudge to Owner action component.
AC 1.2: The Secure Nudge action must only be available to authenticated users with a valid session. Unauthenticated visitors must be prompted to sign in via Google OAuth before proceeding.
AC 1.3: The form must validate that the message body contains between 10 and 500 characters. The finder's email is derived from their authenticated Google OIDC profile and must not be manually entered.
AC 1.4: The system must sanitize the input string to strip out HTML tags and prevent cross-site scripting (XSS) injections before processing.
AC 1.5: GPS coordinate sharing is a Verified tier feature. On the free tier, the nudge form must not offer location capture. A subtle upsell prompt (e.g., "Upgrade to share your location with the owner") may be displayed.
AC 1.6: Upon submission, the platform must display a confirmation message without exposing any part of the owner's email address or phone number.
AC 1.7: A finder may initiate at most 3 nudge sessions per pet within a 24-hour window. Attempts beyond this threshold must be rejected with a clear rate-limit message.
AC 1.8: The system must reject a nudge if the authenticated finder is the pet's registered owner, displaying an appropriate message (e.g., "You cannot nudge yourself").
AC 1.9: If the scanned pet has no registered owner (orphan chip), the Secure Nudge action must be disabled and the interface must display a message (e.g., "This pet has no registered owner — nudge unavailable").

## US-02: Generating the Masked Alert Notification (System Vector)

As a PawsLedger System Engine, I want to capture the finder's form payload, generate a short-lived cryptographically signed token, and email the owner via an institutional relay, So that the owner can receive immediate recovery context without structural latency or data visibility gaps.

### Acceptance Criteria:
* AC 2.1: The backend must resolve the scanned pet_id against the database to extract the underlying owner_id and their registered OIDC email address. The finder's identity must be resolved from the authenticated session (user_id and OIDC email).
* AC 2.2: The system must initialize a NudgeSessionRecord in the database with a strict 48-hour Time-to-Live (TTL) expiration configuration. The record must store the finder's user_id (not a raw email) for auditability.
* AC 2.3: A cryptographic single-use token (response_token) must be generated and appended to an automated template sent from <alerts@pawsledger.com>.
* AC 2.4: The outbound email body must cleanly display the finder's sanitized description and inform the owner that their pet has been found. The finder's email address must not appear in the email body. On the free tier, no callback URL or reply mechanism is included — the email directs the owner to their dashboard to view the nudge.
* AC 2.5: If the email delivery fails (Resend API returns an error), the system must not create the NudgeSessionRecord, and the finder must be shown an explicit failure message (e.g., "Unable to deliver notification. Please try again later.") rather than a false confirmation.
* AC 2.6: The outbound email must use a callback URL on the canonical `pawsledger.com` domain (no URL shorteners or third-party redirects). The email template must include anti-phishing guidance (e.g., "PawsLedger will never ask for your password in this email") to help owners distinguish legitimate alerts from spoofed messages.

## US-03: Owner Nudge Visibility (Free Tier)

As a Pet Owner who has received a recovery alert, I want to see the nudge on my dashboard so that I am aware my pet has been found and can take action outside the platform.

### Acceptance Criteria:
* AC 3.1: The owner's dashboard must display the most recent nudge received per pet, including the finder's sanitized message and timestamp.
* AC 3.2: The owner must not be shown the finder's email address or any PII — only the message content.
* AC 3.3: A prompt must inform the owner that secure two-way messaging is available on the Verified tier (e.g., "Upgrade to reply securely without revealing your email").
* AC 3.4: NudgeSessionRecords on the free tier must be automatically purged after 30 days. Full history and manual deletion controls are available on the Verified tier.
