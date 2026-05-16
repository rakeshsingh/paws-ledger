# Epic: Verified Tier Secure Recovery Messaging

Epic Description: As a PawsLedger Verified tier subscriber, I want bidirectional privacy-preserving messaging, GPS-assisted recovery, and full nudge history so that I can coordinate pet handoffs efficiently through PawsLedger's secure relay without exposing raw PII to either party.

Prerequisites: All free tier functionality (see business_requirements_v1_free_tier_secure_find.md) is included. The Verified tier extends the free tier with the features below.

## US-V01: GPS-Assisted Location Sharing (Finder Vector)

As a Verified tier Pet Finder, I want to share my browser-based GPS coordinates along with my nudge message, so that the pet owner has immediate context about where their pet was found.

### Acceptance Criteria:
* AC V1.1: The nudge form must optionally capture browser-based GPS coordinates (geo_latitude, geo_longitude) only after explicit user permission via the browser's Geolocation API.
* AC V1.2: The interface must clearly disclose that coordinates will be shared with the pet owner before the user grants permission.
* AC V1.3: If GPS permission is denied or unavailable, the nudge must still submit successfully without coordinates.
* AC V1.4: Coordinates must be stored on the NudgeSessionRecord and included in the owner's alert email and dashboard view.
* AC V1.5: Coordinates must be displayed to the owner as a clickable map link (e.g., Google Maps or OpenStreetMap) rather than raw lat/lng values.

## US-V02: Secure Owner Reply Relay (Owner Vector)

As a Verified tier Pet Owner who has received a recovery alert, I want to reply to the finder through a secure, authenticated web form so that my message reaches the finder's inbox while my email address remains hidden behind PawsLedger's proxy relay.

### Acceptance Criteria:
* AC V2.1: The alert email sent to the owner must include an actionable callback URL containing a cryptographic single-use response_token.
* AC V2.2: The callback URL must respond to GET requests by rendering the response form without invalidating the token. Token invalidation must only occur upon a successful POST submission. This prevents email security scanners (e.g., Outlook SafeLinks, Gmail link previews) from consuming the token via automated pre-fetch requests.
* AC V2.3: When the owner clicks the email link, the target route must validate the response_token, verifying that it is structurally intact and that the session has not surpassed its 48-hour expires_at timestamp.
* AC V2.4: The owner must be authenticated via Google OAuth and their authenticated user_id must match the owner_id stored on the NudgeSessionRecord. If the user is not authenticated, they must be redirected to sign in. If the authenticated user does not match the owner, the request must be rejected with a 403 Forbidden.
* AC V2.5: The landing application view must restrict input entry (OwnerResponseInput) to a maximum threshold of 1000 characters.
* AC V2.6: Submitting the response form must immediately trigger an asynchronous transactional message delivered to the finder's verified OIDC email (resolved from their user_id in the NudgeSessionRecord).
* AC V2.7: The message sender string visible to the finder must be masked as PawsLedger Recovery <recovery@pawsledger.com>. The owner's email address must not appear anywhere in the message headers or body visible to the finder.
* AC V2.8: Post-transmission, the database session record state must be permanently toggled to is_resolved = True, and the verification link must immediately invalidate to prevent token reuse or replay vectors.
* AC V2.9: If the token has expired (past 48-hour TTL) or has already been used, the landing page must display a clear "This link has expired" message with guidance directing the owner to ask the finder to send another nudge.
* AC V2.10: The outbound email must use a callback URL on the canonical `pawsledger.com` domain (no URL shorteners or third-party redirects). The email template must include anti-phishing guidance (e.g., "PawsLedger will never ask for your password in this email") to help owners distinguish legitimate alerts from spoofed messages.

## US-V03: Full Nudge History and Lifecycle Management

As a Verified tier user, I want full visibility into my nudge history (sent and received) and the ability to manage my data, so that I can track recovery progress and control my personal information.

### Acceptance Criteria:
* AC V3.1: The finder's dashboard must display all sent nudges with their current status (pending/responded/expired), message preview, timestamp, and pet identifier.
* AC V3.2: The owner's dashboard must display a complete history of nudges received per pet, including the finder's sanitized message, GPS coordinates (if shared), timestamp, and response status.
* AC V3.3: NudgeSessionRecords must be retained for 90 days before automatic purge.
* AC V3.4: Users must be able to manually delete their own nudge history (sent or received) from their dashboard at any time. Deletion must be permanent and irrecoverable.
* AC V3.5: Deleting a nudge record on one side (finder or owner) must not affect the other party's copy of the record.
