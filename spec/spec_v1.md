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
* Auth: Authlib libraryto handle OIDC/social logins.
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
| ----      | ----         | ----    |
| Breed Metadata | TheDogAPI / TheCatAPI | Populating dropdowns and health traits.|
| Manufacturer Codes| ISO 11784 Standards | Identifying chip origin automatically. |
| Vet Clinics |Google Places API| Helping users find and link local vets. |

### 5. API Design (Key Endpoints)

* GET /api/v1/lookup/{chip_id}
Action: Checks the internal database first, then triggers an external meta-search.
Logic: Returns 404 Not Found if the chip is "Unclaimed," triggering the "Claim this Pet" flow.
* POST /api/v1/ledger/transfer
Action: Initiates an ownership handover.
Security: Requires MFA from the current owner and an "Acceptance" token from the new owner.
* GET /api/v1/qr/{tag_id}
Action: Resolves the physical QR scan to the pet's "Public Safety Profile."

### 6. Implementation Roadmap (Spec-Driven)

#### Phase 0: Foundational Components

1. Authentication Stack:
1. The PawsLedger authentication stack is engineered to achieve near-zero operational overhead by delegating identity provisioning and credential management to established Identity Providers (IdPs). Instead of maintaining a legacy user-management database (with the associated risks of salted hashes and reset flows), PawsLedger acts as a Service Provider (SP) that consumes verified identity claims.
2. Handshake Mechanics (Google OIDC Flow) : The system implements the Authorization Code Flow, ensuring that sensitive tokens never touch the user’s browser history or logs.

Initiation: When a user clicks "Sign in with Google," the application generates a state-token to prevent Cross-Site Request Forgery (CSRF) and redirects the browser to the Google OIDC Discovery Document endpoint.

The Redirect: The user authenticates directly on Google's infrastructure. PawsLedger never sees the user's password, effectively outsourcing MFA (Multi-Factor Authentication) and device-trust verification to Google.

The Callback & Exchange: Upon successful login, the IdP sends an authorization code to a secured /auth/callback endpoint. The backend exchanges this code for an ID Token (a signed JWT) via a server-to-server POST request.

3. Stateless Session Management
To maintain a high-performance, horizontally scalable environment, the stack is entirely stateless.

JWT Verification: The backend verifies the ID Token signature locally using the IdP’s public keys (retrieved via the jwks_uri).

Secure Session: Once verified, the application issues its own Session JWT, stored in an HttpOnly, Secure, and SameSite=Lax cookie.

Identity Anchoring: The user's email (verified claim) serves as the immutable anchor in the PawsLedger database, linking the authenticated human to their specific pet records and ledger history.

4. Scope-Driven Privacy (Least Privilege)
To maximize user trust and minimize compliance surface area (GDPR/CCPA), the stack requests the absolute minimum data required for functional integrity:

openid: To receive the ID Token and confirm OIDC compliance.

email: The primary key for account recovery and "Sitter Heartbeat" notifications.

profile (First Name Only): To personalize the Vaccination Report and Caregiver Views without requiring manual data entry.

#### Phase 1: The "Identity Core" (MVP)

* Develop the search landing page to provide a Microchip search interface to tell if the information for a pet is registered on the PetLedger website or not. If not present, make a search call to the nationwide AAHA network to share where all that microchip is registered.
* Build the prefix-mapping logic.
* Implement the QR-to-Profile resolution API, and UI logic.
* Develop the "Public Safety" landing page for lost pets.
* Create few static pages: About, FAQ, and Contact Us
* Build the API and the UI layer to register a pet owner, and register their pets.
* Add support of Social authentication of a pet owner using AuthO
* Build a dashboard page, where a pet owner can see all the pets that they have registered, and see their details (e.g. Name, Species, Breed)

#### Phase 2: The "Health Ledger"

Integrate medical record uploads (PDF parsing using Gen-AI).Build the "Caregiver" time-bound access sharing.

#### Phase 3: The "Ecosystem"

Integrate with insurance providers via API.Launch the "Veri-Tag" physical hardware store.

### 7. Security & Compliance

PII Privacy: Ensure owner contact info is obfuscated until a "Lost" state is explicitly toggled by the user.
Data Portability: Allow users to export their pet’s "Ledger" as a verified JSON or PDF file, preventing vendor lock-in.
