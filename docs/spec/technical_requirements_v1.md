## Technical Specification: PawsLedger v1.0

* Project Codename: PawsLedger
* Architecture Style: Spec-Driven Development / Micro-SaaSCore
* Philosophy: Identity as a Service (IDaaS) for Pets

### 1. System Overview

PawsLedger is a hybrid identity platform that provides a "Single Source of Truth" for pet records. It links a physical identifier (Microchip or QR Tag) to a secure, cloud-based digital ledger.

Core Objectives:

* **Decoupled Identity:** Separate the pet's record from proprietary, fragmented manufacturer databases.
* **Trusted Transfer:** Securely manage change of ownership using cryptographic handshakes.
* **IAM Integration:** Use time-bound access tokens for vets, sitters, and boarding facilities.

### 2. Functional Requirements

#### 2.1 Identity & Registry Management

* **Global Lookup Service (GLS):** An integration layer that queries the AAHA Universal Lookup via scrapers or API (where available) to verify existing registration status.
* **Manufacturer Prefix Mapping:** A lookup table to identify chip manufacturers based on the first 3 digits of the ISO 11784/11785 chip ID.
* **Proof of Ownership (PoO):** A digital certificate generated upon registration, signed with a platform-level private key.

#### 2.2 The "Ledger" (Data Schema)

* **Immutable Logs:** Audit trails for every "Event" (vaccinations, weight checks, ownership changes).
* **Emergency Mode:** A "Public" view of the pet's profile triggered by a QR scan, displaying only critical safety info and "Call Owner" buttons.

#### 2.3 Access Control (IAM)

* **The "Guardian" Role:** Full CRUD permissions (the owner).
* **The "Caregiver" Role:** Read-only access to medical/dietary info, valid for a configurable number of days.
* **The "Vet" Role:** Permission to "Sign" medical events in the ledger.

### 3. Technical Architecture

#### 3.1 Tech Stack

| Layer | Technology | Rationale |
| ----- | ---------- | --------- |
| Backend | Python (FastAPI) | High-speed async API development |
| Database | SQLite (via SQLModel) | Lightweight relational store for pet data |
| Auth | Authlib (OIDC) | Handles Google/Apple social logins |
| Frontend | NiceGUI | Python-native UI, no separate JS build step |
| External APIs | TheDogAPI | Breed metadata during pet registration |

#### 3.2 System Architecture Diagram

*(To be added)*

### 4. Data Models

#### 4.1 Pet Record Schema

```json
{
  "id": "UUID",
  "chip_id": "STRING (15-digit ISO 11784/11785)",
  "manufacturer": "STRING (derived from 3-digit prefix)",
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
| --------- | ------------ | ------- |
| Breed Metadata | TheDogAPI / TheCatAPI | Populating dropdowns and health traits |
| Manufacturer Codes | ISO 11784 Standards | Identifying chip origin automatically |
| Vet Clinics | Google Places API | Helping users find and link local vets |

### 5. API Design (Key Endpoints)

| Method | Endpoint | Description |
| ------ | -------- | ----------- |
| `GET` | `/api/v1/lookup/{chip_id}` | Checks internal DB first, then triggers AAHA meta-search. Returns 404 if unclaimed, triggering the "Claim this Pet" flow. |
| `POST` | `/api/v1/ledger/transfer` | Initiates ownership handover. Requires MFA from current owner and an acceptance token from the new owner. |
| `GET` | `/api/v1/qr/{tag_id}` | Resolves a physical QR scan to the pet's public safety profile. |

### 6. Implementation Roadmap

#### Phase 0: Foundational Components

Phase 0 establishes the core infrastructure that every subsequent feature depends on: identity anchoring, zero-password authentication, the public recovery page, the vaccination ledger, and managed access for service providers.

##### 0.1 The Identity Foundation

The foundation of the system is a high-integrity mapping between a physical animal and a verified human owner.

* **ISO-ID Mapping:** A database schema that stores a 15-digit ISO-compliant microchip ID as the primary key for each pet record. The first 3 digits resolve to a manufacturer via a prefix lookup table.
* **Digital Passport:** A centralized "Source of Truth" that links microchip data, owner OIDC claims, and medical records for a given pet.

##### 0.2 Zero-Password Authentication (OIDC)

To eliminate password liability and minimize operational overhead, PawsLedger delegates all credential management to established Identity Providers (IdPs). The platform acts as a Service Provider (SP) that consumes verified identity claims — it never sees or stores user passwords.

**Supported Providers:** Google and Apple Social Auth (via OIDC).

**Authorization Code Flow:**

1. **Initiation:** When a user clicks "Sign in with Google," the app generates a `state` token (CSRF protection) and redirects the browser to the Google OIDC Discovery Document endpoint.
2. **IdP Authentication:** The user authenticates directly on Google's infrastructure. PawsLedger never handles credentials, effectively outsourcing MFA and device-trust verification to the IdP.
3. **Callback & Token Exchange:** On success, the IdP sends an authorization code to a secured `/auth/callback` endpoint. The backend exchanges this code for an ID Token (a signed JWT) via a server-to-server POST request.
4. **JWT Verification:** The backend verifies the ID Token signature locally using the IdP's public keys (retrieved via the `jwks_uri`).

**Hybrid Session Management:**

* PawsLedger uses a hybrid session architecture combining two complementary mechanisms:
  * **NiceGUI Server-Side Storage (`app.storage.user`):** Maintains reactive UI state (email, name, id, greet_user flag) keyed by a browser-managed session cookie. This is required by NiceGUI's server-side rendering model and enables real-time UI updates.
  * **HMAC-Signed `paws_user_id` Cookie:** An `HttpOnly`, `Secure`, `SameSite=Lax` cookie containing the user's UUID signed via `itsdangerous.URLSafeSerializer`. This cookie is used for API-layer user identification (e.g., the `/api/v1/me` endpoint) and is verified by unsigning with the application secret key.
* The user's verified email serves as the immutable anchor in the PawsLedger database, linking the authenticated human to their pet records and ledger history.
* **Scaling Note:** Because NiceGUI's `app.storage.user` is server-side state, horizontal scaling requires either sticky sessions (session affinity) or a shared session store (e.g., Redis) to ensure UI state consistency across instances. The signed cookie for API identification is stateless and does not impose this constraint.

**Scope-Driven Privacy (Least Privilege):**

The stack requests the minimum data required for functional integrity, minimizing GDPR/CCPA compliance surface area:

| Scope | Purpose |
| ----- | ------- |
| `openid` | Receive the ID Token and confirm OIDC compliance |
| `email` | Primary key for account recovery and caregiver notifications |
| `profile` (first name only) | Personalize vaccination reports and caregiver views |

##### 0.3 PawsPage & Scan Alerts (Recovery)

The public-facing utility that proves the platform's value to the community.

* **Public Recovery UI (PawsPage):** A mobile-optimized landing page accessible via QR code. Displays critical medical and dietary information plus a "Contact Owner" option. Owner PII is never shown publicly — the PawsLedger backend sends an email to the owner on the user's behalf.
* **Instant Scan Notifications:** A backend trigger that emails the owner the moment their pet's page is accessed, providing immediate "proof of life" if a pet is found.

##### 0.4 The Vaccination Ledger (Compliance)

The feature that provides daily utility and long-term retention for users.

* **NASPHV Form 51 Compliance:** Structured data entry to capture vaccination history for rabies and core shots, mirroring the US national standard.
* **Verified PDF Export:** A tamper-evident PDF generator that includes a SHA-256 cryptographic hash, allowing third parties to verify the record's authenticity via the PawsLedger backend.

##### 0.5 Managed Access for Service Providers ("Heartbeats")

Shareable, time-bound URLs for service providers (groomers, walkers, pet-sitters) to view a pet's vaccination history, dietary preferences, and other care information.

* **Time-Bound Tokens (TTL):** The ability to generate 24-hour or 48-hour access links for sitters or groomers.
* **Heartbeat Audit:** A real-time notification sent to the owner when the caregiver accesses the care guide or medical records, serving as a digital "proof of service."

---

#### Phase 1: The "Identity Core" (MVP)

Building on the Phase 0 foundation, Phase 1 delivers the minimum viable product:

* Develop the search landing page with a microchip search interface to check if a pet is registered on PawsLedger. If not present, query the nationwide AAHA network to show where the chip is registered.
* Build the manufacturer prefix-mapping logic.
* Implement the QR-to-Profile resolution API and UI.
* Develop the "Public Safety" landing page for lost pets.
* Create static pages: About, FAQ, and Contact Us.
* Build the API and UI layer to register a pet owner and their pets.
* Add social authentication for pet owners using Authlib (Google OIDC).
* Build a dashboard page where a pet owner can see all registered pets and their details (name, species, breed).

#### Phase 2: The "Health Ledger"

* Integrate medical record uploads (PDF parsing using Gen-AI).
* Build the "Caregiver" time-bound access sharing.

#### Phase 3: The "Ecosystem"

* Integrate with insurance providers via API.
* Launch the "Veri-Tag" physical hardware store.

### 7. Security & Compliance

* **PII Privacy:** Owner contact info is obfuscated until a "Lost" state is explicitly toggled by the user.
* **Data Portability:** Users can export their pet's "Ledger" as a verified JSON or PDF file, preventing vendor lock-in.
