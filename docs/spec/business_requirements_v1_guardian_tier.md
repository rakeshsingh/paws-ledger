# Epic: Guardian Tier — Total Peace of Mind

Epic Description: As a PawsLedger Guardian tier subscriber ($4.99/month or $49.99/year), I want all Verified tier features plus unlimited document storage, automated alert delivery (email/SMS), service provider heartbeat monitoring, tamper-proof medical documents, lost pet alert broadcast, and emergency vet authorization — so that I have the most comprehensive pet protection available.

Prerequisites: All Verified tier functionality (see business_requirements_v1_verified_tier.md) is included. The Guardian tier extends the Verified tier with the features below.

---

## US-G01: Unlimited Document Storage

As a Guardian tier Pet Owner, I want to upload up to 100 documents per pet so that I can maintain a complete archive of veterinary certificates, lab results, insurance paperwork, and travel health documents.

### Acceptance Criteria:
* AC G1.1: Guardian tier users may upload up to 100 documents per pet (PDF, JPEG, PNG, WebP, up to 10MB each), compared to the Verified tier limit of 1 document per pet.
* AC G1.2: The system must display the current document count and remaining capacity (e.g., "3 of 100 documents used").
* AC G1.3: Documents must be individually deletable by the owner.
* AC G1.4: All documents must be stored in Cloudflare R2 with the key pattern `vaccinations/{pet_id}/{filename}`.

---

## US-G02: Automated Alert Delivery (Email & SMS)

As a Guardian tier Pet Owner, I want my configured vaccination and appointment alerts to be automatically sent to me via email (and optionally SMS) on the scheduled date so that I never miss a critical health milestone.

### Acceptance Criteria:
* AC G2.1: On the Guardian tier, all alerts configured by the owner (see US-V07) must be delivered via email on the alert_date.
* AC G2.2: The owner may optionally provide a phone number to receive SMS alerts in addition to email.
* AC G2.3: The alert email must include: pet name, alert title, description (if set), and a direct link to the pet's profile page.
* AC G2.4: SMS alerts must be concise (under 160 characters) and include the pet name, alert title, and a shortened link.
* AC G2.5: Delivered alerts must be marked as is_sent = True to prevent duplicate delivery.
* AC G2.6: If email delivery fails, the system must retry once after 1 hour. If SMS delivery fails, no retry is attempted (best-effort).
* AC G2.7: The Verified tier must NOT send automated alerts — only display them on the dashboard with a prompt to upgrade.

---

## US-G03: Service Provider Heartbeat (Sitter/Groomer Check-ins)

As a Guardian tier Pet Owner, I want to receive real-time notifications whenever a service provider (sitter, groomer, boarder) accesses my pet's shared care link so that I know they've reviewed the instructions and my pet is being attended to.

### Acceptance Criteria:
* AC G3.1: Every shared link access must trigger an immediate email notification to the owner (in addition to the audit log).
* AC G3.2: The notification must include: accessor context (e.g., "Shared Link accessed"), pet name, timestamp, and a link to the pet's audit trail.
* AC G3.3: The owner's dashboard must display a "Last checked in" indicator per active shared link.
* AC G3.4: Guardian tier owners must have unlimited shared link generation (no cap on concurrent active links). Verified tier is limited to 5 active links per pet.

---

## US-G04: Tamper-Proof Medical Documents (SHA-256 Signed PDFs)

As a Guardian tier Pet Owner, I want to export my pet's vaccination records as a cryptographically signed PDF so that veterinary clinics, border agencies, and insurance companies can verify the document's authenticity.

### Acceptance Criteria:
* AC G4.1: The exported PDF must include a SHA-256 hash of all vaccination data in the document footer.
* AC G4.2: The PDF must include a verification URL (e.g., `https://www.pawsledger.com/verify?hash=...`) that anyone can visit to confirm the hash matches the current records.
* AC G4.3: The PDF header must display "PawsLedger Certified Vaccination Record" with the export timestamp.
* AC G4.4: If any vaccination record is modified after export, the verification URL must indicate the document is out of date.
* AC G4.5: Verified tier users may export PDFs but without the signed verification URL (basic export only).

---

## US-G05: Lost Pet Alert Broadcast

As a Guardian tier Pet Owner, I want to broadcast a "lost pet" alert to other PawsLedger users in my area so that nearby users can help watch for my pet.

### Acceptance Criteria:
* AC G5.1: The owner must be able to mark a pet as "LOST" from their pet's profile page, providing a last-seen location and optional description.
* AC G5.2: When a pet is marked as lost, the system must notify all Guardian tier users within a configurable radius (default 15 km) of the last-seen location via email.
* AC G5.3: The broadcast must include: pet photo (if available), species, breed, color description, last-seen location (as a map link), and the pet's public profile URL.
* AC G5.4: Recipients must not receive the owner's personal contact information — they can use the existing nudge system to report a sighting.
* AC G5.5: The owner must be able to cancel the alert (mark as "FOUND") which sends a follow-up "pet recovered" notification to all previously notified users.
* AC G5.6: A maximum of 1 active lost alert per pet at a time.

---

## US-G06: Emergency Vet Authorization Card

As a Guardian tier Pet Owner, I want to pre-generate a digitally signed emergency authorization document so that a sitter or family member can authorize veterinary treatment on my behalf if I'm unreachable.

### Acceptance Criteria:
* AC G6.1: The owner must be able to create an emergency authorization card specifying: authorized person's name, relationship, maximum treatment cost cap, pet's medical history summary, preferred emergency vet, and validity period (1 day to 30 days).
* AC G6.2: The authorization card must be generated as a sealed PDF with a SHA-256 hash and a QR code linking to an online verification page.
* AC G6.3: The authorized person must be able to access the card via a unique, time-limited URL without requiring a PawsLedger account.
* AC G6.4: The card must clearly state it is not a legal document but an expression of the owner's intent, and that the vet should use professional judgment.
* AC G6.5: Expired authorization cards must display "Authorization Expired" when accessed.
* AC G6.6: The owner must be able to revoke an active card at any time from their dashboard.
