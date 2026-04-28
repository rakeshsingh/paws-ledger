## Technical Specification: PawsLedger v1.0
* Project Codename: PawsLedger
* Architecture Style: Spec-Driven Development / Micro-SaaSCore 
* Philosophy: Identity as a Service (IDaaS) for Pets
### 1. System Overview
PawsLedger is a hybrid identity platform that provides a "Single Source of Truth" for pet records. It links a physical identifier (Microchip or QR Tag) to a secure, cloud-based digital ledger.
Core Objectives:
* Decoupled Identity: Separate the pet’s record from proprietary, fragmented manufacturer databases.
* Trusted Transfer: Securely manage change of ownership using cryptographic handshakes.
* IAM Integration: Use time-bound access tokens for vets, sitters, and boarding facilities.
### 2. Functional Requirements
#### 2.1 Identity & Registry Management
* The Global Lookup Service (GLS): An integration layer that queries the AAHA Universal Lookup via scrapers or API (where available) to verify existing registration status.
* Manufacturer Prefix Mapping: A lookup table to identify chip manufacturers based on the first 3-digits of the ISO 11784/11785 chip
* Proof of Ownership (PoO): A digital certificate generated upon registration, signed with a platform-level private key.

#### 2.2 The "Ledger" (Data Schema)
* Immutable Logs: Audit trails for every "Event" (Vaccinations, weight checks, ownership changes).
* Emergency Mode: A "Public" view of the pet's profile triggered by a QR scan, displaying only critical safety info and "Call Owner" buttons.
#### 2.3 Access Control (IAM)
* The "Guardian" Role: Full CRUD permissions (The Owner).
* The "Caregiver" Role: Read-only access to medical/dietary info, valid for $X$ days.
* The "Vet" Role: Permission to "Sign" medical events in the ledger.
### 3. Technical Architecture
#### 3.1 Tech Stack (Recommended for Gen-AI Dev)
* Backend: Python (FastAPI) for high-speed API development.
* Database: SQLITE (for relational pet data) 
* Auth: Auth0 or Clerk (to handle OIDC/social logins).
* Frontend: Python NiceGUI
* External Libraries: Use DogAPI while registering the Chip information of a new Dog
#### 3.2 System Architecture Diagram

### 4. Data Models (Seed Strategy)
#### 4.1 Pet Record SchemaJSON

```json
{
  "id": "UUID",
  "chip_id": "STRING (15-digit)",
  "manufacturer": "STRING (derived from prefix)",
  "identity_status": "VERIFIED | UNVERIFIED",
  "owner_id": "USER_UUID",
  "pet_species": "STRING (defaults to DOG)",
  "attributes": {
    "breed": "STRING (sourced from TheDogAPI)",
    "dob": "TIMESTAMP",
    "weight_history": "ARRAY<LOGS>"
  },
  "ledger_events": "ARRAY<EVENTS>"
}
```

#### 4.2 Bootstrap Sources (Seed Data)
| Data Type | Source / API | Purpose |
| ----      | ----         | ---|
| Breed MetadataTheDogAPI / TheCatAPIPopulating dropdowns and health traits.Manufacturer CodesISO 11784 StandardsIdentifying chip origin automatically.Vet ClinicsGoogle Places APIHelping users find and link local vets.

### 5. API Design (Key Endpoints)GET /api/v1/lookup/{chip_id}Action: Checks the internal database first, then triggers an external meta-search.Logic: Returns 404 Not Found if the chip is "Unclaimed," triggering the "Claim this Pet" flow.POST /api/v1/ledger/transferAction: Initiates an ownership handover.Security: Requires MFA from the current owner and an "Acceptance" token from the new owner.GET /api/v1/qr/{tag_id}Action: Resolves the physical QR scan to the pet's "Public Safety Profile."

### 6. Implementation Roadmap (Spec-Driven)
* Phase 1: The "Ide:wqntity Core" (MVP)Build the prefix-mapping logic.Implement the QR-to-Profile resolution.Develop the "Public Safety" landing page for lost pets.
* Phase 2: The "Health Ledger"Integrate medical record uploads (PDF parsing using Gen-AI).Build the "Caregiver" time-bound access sharing.
* Phase 3: The "Ecosystem"Integrate with insurance providers via API.Launch the "Veri-Tag" physical hardware store.
### 7. Security & Compliance
PII Privacy: Ensure owner contact info is obfuscated until a "Lost" state is explicitly toggled by the user.
Data Portability: Allow users to export their pet’s "Ledger" as a verified JSON or PDF file, preventing vendor lock-in.