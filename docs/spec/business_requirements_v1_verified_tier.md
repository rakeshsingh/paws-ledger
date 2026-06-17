# Epic: Verified Tier — Secure Recovery, Care Sharing & Ownership Management

Epic Description: As a PawsLedger Verified tier subscriber ($4.99/year), I want bidirectional privacy-preserving messaging, GPS-assisted recovery, shareable pet care guides for sitters, vaccination management with alerts, verified identity badges, and secure ownership transfers — so that I can fully protect my pet's identity, coordinate care with service providers, and manage recovery efficiently.

Prerequisites: All free tier functionality (see business_requirements_v1_free_tier.md) is included. The Verified tier extends the free tier with the features below.

---

## US-V01: GPS-Assisted Location Sharing (Finder Vector)

As a Verified tier Pet Finder, I want to share my browser-based GPS coordinates along with my nudge message, so that the pet owner has immediate context about where their pet was found.

### Acceptance Criteria:
* AC V1.1: The nudge form must optionally capture browser-based GPS coordinates (geo_latitude, geo_longitude) only after explicit user permission via the browser's Geolocation API.
* AC V1.2: The interface must clearly disclose that coordinates will be shared with the pet owner before the user grants permission.
* AC V1.3: If GPS permission is denied or unavailable, the nudge must still submit successfully without coordinates.
* AC V1.4: Coordinates must be stored on the NudgeSessionRecord and included in the owner's alert email and dashboard view.
* AC V1.5: Coordinates must be displayed to the owner as a clickable map link (e.g., Google Maps or OpenStreetMap) rather than raw lat/lng values.

---

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

---

## US-V03: Full Nudge History and Lifecycle Management

As a Verified tier user, I want full visibility into my nudge history (sent and received) and the ability to manage my data, so that I can track recovery progress and control my personal information.

### Acceptance Criteria:
* AC V3.1: The finder's dashboard must display all sent nudges with their current status (pending/responded/expired), message preview, timestamp, and pet identifier.
* AC V3.2: The owner's dashboard must display a complete history of nudges received per pet, including the finder's sanitized message, GPS coordinates (if shared), timestamp, and response status.
* AC V3.3: NudgeSessionRecords must be retained for 90 days before automatic purge.
* AC V3.4: Users must be able to manually delete their own nudge history (sent or received) from their dashboard at any time. Deletion must be permanent and irrecoverable.
* AC V3.5: Deleting a nudge record on one side (finder or owner) must not affect the other party's copy of the record.

---

## US-V04: Shareable Pet Care Guide for Service Providers

As a Verified tier Pet Owner, I want to create a structured, shareable care guide for my pet so that any sitter, groomer, or caregiver has immediate access to feeding schedules, medications, behavioral notes, and emergency contacts — without me needing to repeat instructions every time.

### Acceptance Criteria:
* AC V4.1: The owner must be able to create care instructions organized by category (feeding, medication, exercise, behavior, emergency), each with a title, content body (up to 2000 characters), and priority level (normal, important, critical).
* AC V4.2: Care instructions must be editable and deletable by the owner at any time.
* AC V4.3: Care instructions must be included in the shared access link view (see US-V05) so service providers see them alongside vaccination records and pet info.
* AC V4.4: Critical-priority instructions must be visually highlighted (e.g., red icon/badge) to draw immediate attention from the caregiver.
* AC V4.5: The system must support at minimum: feeding portions/times, medication name/dosage/schedule, exercise requirements, behavioral quirks/triggers, and emergency vet contact info.

---

## US-V05: Time-Bound Shared Access Links

As a Verified tier Pet Owner, I want to generate a temporary, shareable link that gives a service provider read-only access to my pet's care guide, vaccination records, and basic identity — so that I don't need to manually re-send information every time I use a sitter.

### Acceptance Criteria:
* AC V5.1: The owner must be able to generate a shared access link with a configurable duration (1 hour to 7 days, default 24 hours).
* AC V5.2: The shared link must not require the recipient to have a PawsLedger account or download any app.
* AC V5.3: The shared link must display: pet name, species, breed, date of birth, chip ID, vaccination records (name, date, expiry status), care instructions (all categories), dietary notes, medical conditions, and emergency alerts.
* AC V5.4: The owner must be notified via email each time the shared link is accessed (heartbeat audit).
* AC V5.5: Expired links must display a clear "Access Expired" message directing the visitor to request a new link from the owner.
* AC V5.6: The shared access page must be mobile-optimized and load without JavaScript dependency for the core content.

---

## US-V06: Guide View Analytics & Access Notifications

As a Verified tier Pet Owner, I want to know when my sitter actually opens and reads the care guide so that I have peace of mind that they've reviewed the instructions.

### Acceptance Criteria:
* AC V6.1: Every access to a shared link must be logged as a HEARTBEAT_ACCESS event in the pet's audit trail with timestamp.
* AC V6.2: The owner must receive a real-time email notification when the shared link is first opened.
* AC V6.3: The owner's dashboard or pet profile must display a "Last accessed" timestamp for each active shared link.
* AC V6.4: Multiple accesses from the same session within 5 minutes must be deduplicated (count as one access event).

---

## US-V07: Vaccination & Appointment Alerts (Configuration & Viewing)

As a Verified tier Pet Owner, I want to configure and view reminders for upcoming vaccinations and appointments on my dashboard so that I can plan ahead — knowing that automated email/SMS delivery of these alerts is available on the Guardian tier.

### Acceptance Criteria:
* AC V7.1: The owner must be able to create custom alerts tied to a specific pet, with a title, date, optional description, and alert type (vaccination_expiry or appointment).
* AC V7.2: When a vaccination record is added, the system should automatically suggest creating an alert 30 days before the expiration date.
* AC V7.3: Alerts must be visible on the owner's dashboard (upcoming alerts within 30 days) with urgency color-coding (overdue = red, within 7 days = amber, otherwise neutral).
* AC V7.4: The owner must be able to delete alerts manually.
* AC V7.5: On the Verified tier, alerts are view-only (displayed on the dashboard). The system must NOT send email or SMS notifications for alerts on this tier. A prompt must inform the user that automated alert delivery is a Guardian tier feature (e.g., "Upgrade to Guardian for email & SMS reminders").
* AC V7.6: On the Guardian tier, alerts must be sent via email (and optionally SMS) on the specified alert_date. The email must include the pet's name, the alert title, and a link to the pet's profile.
* AC V7.7: Sent alerts (Guardian tier only) must be marked as is_sent = True to prevent duplicate delivery.

---

## US-V08: Vaccination Record Storage & Document Upload

As a Verified tier Pet Owner, I want to store vaccination records digitally and upload a supporting document (PDF or photo of certificate) so that I have a portable medical record for my pet.

### Acceptance Criteria:
* AC V8.1: Verified tier users may store up to 20 vaccination records per pet (Standard storage).
* AC V8.2: Each vaccination record must capture: vaccine name, manufacturer, serial/lot number, date given, expiration date, administering vet, and clinic name.
* AC V8.3: Each record must be hashed (SHA-256) upon creation for tamper detection.
* AC V8.4: Verified tier users may upload a maximum of 1 document per pet (PDF, JPEG, PNG, WebP, up to 10MB), stored in Cloudflare R2. Guardian tier users may upload up to 100 documents per pet.
* AC V8.5: The system must enforce the per-tier document limit and display a clear message when the limit is reached (e.g., "Upgrade to Guardian for additional document storage").
* AC V8.6: Uploaded documents must be accessible from the pet's profile page and included in PDF exports.
* AC V8.7: The owner must be able to export all vaccination records as a PDF report with a verification hash footer.

---

## US-V09: Verified Identity Badge

As a Verified tier Pet Owner, I want a visible "Verified" badge on all my pet profiles so that finders and service providers can trust that the pet's records are maintained by an active, paying subscriber.

### Acceptance Criteria:
* AC V9.1: All pets belonging to a user with an active Verified or Guardian subscription must display a green "Verified" badge on their profile (both public and private views).
* AC V9.2: The badge must be derived from the user's live subscription status — not a cached field. If the subscription lapses, the badge must revert to "Unverified" on the next page load.
* AC V9.3: The badge must also appear on pet cards in the owner's dashboard.
* AC V9.4: The public pet profile must show "Active Record" status when verified, and "Unverified" otherwise.

---

## US-V10: Periodic Contact Update Reminders

As a Verified tier Pet Owner, I want periodic reminders to verify my contact information is current so that if my pet is ever lost, I can be reached without delay.

### Acceptance Criteria:
* AC V10.1: The system must send a contact verification reminder email to verified users every 90 days, unless their profile was updated within that period.
* AC V10.2: The email must link directly to the owner's profile edit page.
* AC V10.3: Users who have updated their profile within the last 90 days must be skipped (no redundant reminders).
* AC V10.4: The reminder must be triggered by a scheduled cron job hitting a protected API endpoint (authenticated via a shared secret header).
* AC V10.5: The system must track the last reminder date (contact_reminded_at) to prevent duplicate sends within the same cycle.

---

## US-V11: Secure Ownership Transfer with Audit Trail

As a Verified tier Pet Owner, I want to transfer ownership of my pet to another person with a full audit trail so that rehoming is recorded, provenance is maintained, and the new owner can prove legitimate acquisition.

### Acceptance Criteria:
* AC V11.1: The owner must be able to initiate a transfer by providing the new owner's email address and optional notes.
* AC V11.2: The system must send an email to the new owner with a unique, time-limited (7 days) acceptance link.
* AC V11.3: The new owner must be authenticated and their email must match the intended recipient before the transfer is executed.
* AC V11.4: Upon acceptance, pet.owner_id must be updated, and a OWNERSHIP_CHANGE event must be logged in the pet's audit trail recording both the previous and new owner.
* AC V11.5: Only one pending transfer per pet may exist at a time. Attempting a second transfer must be rejected.
* AC V11.6: Expired transfers must be automatically marked as "expired" when accessed after the 7-day window.
* AC V11.7: The owner must be able to view the full transfer history for any of their pets (date, recipient email, status, notes).

---

## US-V12: Pet Profile Photo Upload

As a Verified tier Pet Owner, I want to upload a profile photo for my pet so that my pet's profile looks personalized and is easier to identify visually by finders and service providers.

### Acceptance Criteria:
* AC V12.1: The owner must be able to upload a profile photo (JPEG, PNG, or WebP, max 5MB) from the pet's profile page.
* AC V12.2: The uploaded photo must be stored in Cloudflare R2 and served via a public or presigned URL.
* AC V12.3: The photo must replace the default species icon placeholder on the pet profile (both public and private views) and on the dashboard pet cards.
* AC V12.4: The owner must be able to remove the photo, reverting to the default species icon.
* AC V12.5: Photo upload must be gated behind an active Verified or Guardian subscription. Free tier users must see the species icon with no upload option.

---

## US-V13: Stripe Subscription Management

As a PawsLedger user, I want to subscribe to the Verified tier via a secure payment flow and manage my subscription (view status, cancel, update payment method) so that I can access premium features.

### Acceptance Criteria:
* AC V13.1: The pricing page must display all tiers with a clear feature comparison and a "Go Verified" CTA that initiates a Stripe Checkout session.
* AC V13.2: After successful payment, the user must be redirected to a success page confirming their subscription is active and listing newly unlocked features.
* AC V13.3: The user must be able to access Stripe's Billing Portal from the subscription management page to update payment methods, view invoices, or cancel.
* AC V13.4: Subscription lifecycle events (activation, renewal, cancellation, payment failure) must be handled via Stripe webhooks and reflected in the user's subscription record within 60 seconds.
* AC V13.5: If a subscription is canceled, it must remain active until the end of the current billing period (cancel_at_period_end). After expiry, all verified features must gracefully degrade to free tier behavior.
* AC V13.6: Failed payments must set the subscription status to "past_due" and the user must be notified via email.
