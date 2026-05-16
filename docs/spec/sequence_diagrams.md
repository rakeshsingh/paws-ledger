# PawsLedger — Sequence Diagrams

## 1. User Authentication (Google OAuth)

```mermaid
sequenceDiagram
    participant U as User (Browser)
    participant N as NiceGUI (Frontend)
    participant F as FastAPI (Backend)
    participant G as Google OAuth

    U->>N: Click "Login"
    N->>F: GET /api/v1/auth/login
    F->>G: Redirect to Google consent screen
    G->>U: Show consent screen
    U->>G: Approve access
    G->>F: GET /api/v1/auth/callback?code=...&state=...
    F->>G: POST /token (exchange code for access token)
    G-->>F: Access token + ID token
    F->>G: GET /userinfo
    G-->>F: User profile (sub, email, name)
    F->>F: Create/find user in DB
    F->>U: Set paws_user_id cookie + Redirect to /dashboard
    U->>N: Load /dashboard
    N->>N: Restore session from cookie (try_restore_session)
    N-->>U: Render dashboard
```

## 2. Microchip Lookup (Landing Page Search)

```mermaid
sequenceDiagram
    participant U as User (Browser)
    participant N as NiceGUI (Frontend)
    participant F as FastAPI (Backend)
    participant DB as SQLite
    participant AAHA as AAHA Network (Mock)

    U->>N: Type chip ID in search bar
    N->>N: get_chip_prefix_info() — show manufacturer hint
    N-->>U: "🔍 Datamars / HomeAgain"
    U->>N: Click "Search"
    N->>DB: SELECT * FROM pet WHERE chip_id = ?
    alt Pet found locally
        DB-->>N: Pet record
        N-->>U: Show pet info + "View Full Ledger" button
    else Not in local DB
        N->>AAHA: lookup(chip_id)
        alt Found in AAHA
            AAHA-->>N: External registry data
            N-->>U: Show AAHA result + "Register This Pet" button
        else Not found anywhere
            AAHA-->>N: None
            N-->>U: "No registration found"
        end
    end
```

## 3. Pet Registration

```mermaid
sequenceDiagram
    participant U as Owner (Browser)
    participant N as NiceGUI (Frontend)
    participant API as Dog CEO API
    participant DB as SQLite

    U->>N: Navigate to /register
    N->>N: Check auth (try_restore_session)
    N->>API: GET /api/breeds/list/all
    API-->>N: List of dog breeds
    N-->>U: Render registration form (4 sections)
    U->>N: Fill form + Submit
    N->>N: Validate chip ID format (9-15 alphanumeric)
    N->>DB: Check chip uniqueness
    N->>DB: Check owner pet count (max 5)
    N->>DB: INSERT pet + optional tag
    DB-->>N: Pet created
    N-->>U: Redirect to /dashboard
```

## 4. QR/NFC Tag Scan (Emergency Profile)

```mermaid
sequenceDiagram
    participant F as Finder (Phone)
    participant N as NiceGUI / FastAPI
    participant DB as SQLite
    participant E as Email Service (Resend)

    F->>N: Scan QR/NFC tag → GET /qr/{tag_code}
    N->>DB: SELECT * FROM pettag WHERE tag_code = ?
    alt Tag found and ACTIVE
        DB-->>N: Tag → Pet record
        N->>DB: INSERT ledger_event (EMERGENCY_SCAN)
        N->>E: notify_owner_of_scan(owner_email)
        E-->>N: Email sent
        N-->>F: Render emergency profile (breed, chip, vaccinations)
    else Tag deactivated
        N-->>F: 410 "Tag is no longer active"
    else Tag not found
        N-->>F: 404 "Tag not registered"
    end
```

## 5. Nudge Owner (Found Pet Flow)

```mermaid
sequenceDiagram
    participant F as Finder (Logged In)
    participant N as NiceGUI (Frontend)
    participant API as FastAPI (Backend)
    participant DB as SQLite
    participant E as Email Service (Resend)

    F->>N: Click "Email Owner" on pet profile
    N->>API: POST /api/v1/nudge/{chip_id}
    API->>API: Verify authentication (cookie)
    API->>API: Validate chip ID format
    API->>DB: SELECT pet + owner WHERE chip_id = ?
    alt Owner has email
        API->>E: send_email(owner, "Someone found your pet!")
        E-->>API: Sent
    end
    API-->>N: "If the owner has notifications enabled, they have been alerted."
    N-->>F: Success notification
```

## 6. Shared Access (24h Care Link)

```mermaid
sequenceDiagram
    participant O as Owner
    participant N as NiceGUI (Frontend)
    participant DB as SQLite
    participant V as Vet/Sitter
    participant E as Email Service

    O->>N: Click "Create 24h Care Link"
    N->>DB: INSERT shared_access (token, expires_at)
    DB-->>N: Token generated
    N-->>O: Show full URL (https://www.pawsledger.com/shared/{token})
    O->>V: Share link via message/email

    Note over V: Within 24 hours...

    V->>N: GET /api/v1/shared/{token}
    N->>DB: SELECT shared_access WHERE token = ?
    alt Token valid and not expired
        DB-->>N: Pet data + vaccinations
        N->>DB: INSERT ledger_event (HEARTBEAT_ACCESS)
        N->>E: notify_owner_of_access(owner_email)
        N-->>V: Pet species, breed, DOB, vaccinations
    else Token expired or invalid
        N-->>V: 403 "Access link expired or invalid"
    end
```

## 7. Vaccination Record Addition

```mermaid
sequenceDiagram
    participant O as Owner
    participant N as NiceGUI (Frontend)
    participant DB as SQLite

    O->>N: Open pet profile → Vaccination Ledger
    N->>N: Load vaccine dropdown from JSON (AAHA guidelines)
    N-->>O: Show form with species-specific vaccines
    O->>N: Fill vaccine rows + Click "Save Vaccination Records"
    loop For each vaccine row
        N->>N: Validate (name, date_given, expiration required)
        N->>N: Calculate SHA-256 record hash
        N->>DB: INSERT vaccination + ledger_event
    end
    DB-->>N: Records saved
    N-->>O: "X vaccination record(s) added!" + Reload page
```

## 8. Tag Management (Add/Deactivate/Remove)

```mermaid
sequenceDiagram
    participant O as Owner
    participant N as NiceGUI (Frontend)
    participant API as FastAPI (Backend)
    participant DB as SQLite

    O->>N: Open pet profile → NFC/QR Tags section
    O->>N: Click "Add New Tag" → Fill form
    N->>API: POST /api/v1/pets/{pet_id}/tags
    API->>API: Verify ownership
    API->>DB: Check tag_code uniqueness
    API->>DB: INSERT pettag + ledger_event (TAG_ACTIVATED)
    API-->>N: Tag created (code, qr_url)
    N-->>O: "Tag added successfully!" + Reload

    Note over O: Later, tag is lost...

    O->>N: Click deactivate icon on tag row
    N->>API: PUT /api/v1/pets/{pet_id}/tags/{tag_id} {status: "DEACTIVATED"}
    API->>API: Verify ownership
    API->>DB: UPDATE pettag SET status = DEACTIVATED
    API->>DB: INSERT ledger_event (TAG_DEACTIVATED)
    API-->>N: Updated
    N-->>O: "Tag deactivated" + Reload
```

## 9. Owner Profile Update

```mermaid
sequenceDiagram
    participant O as Owner
    participant N as NiceGUI (Frontend)
    participant DB as SQLite

    O->>N: Navigate to /owner/profile
    N->>N: Restore session (try_restore_session)
    N->>DB: SELECT user WHERE email = ?
    DB-->>N: User data (name, email, phone, city, country, address)
    N-->>O: Render view mode

    O->>N: Click "Edit Profile"
    N-->>O: Switch to edit mode (inline form)
    O->>N: Modify fields + Click "Save Changes"
    N->>DB: UPDATE user SET name=?, email=?, phone=?, city=?, country=?, address=?
    DB-->>N: Updated
    N->>N: Update session storage
    N-->>O: "Profile updated successfully!" + Switch to view mode
```

## 10. Deployment & Request Flow

```mermaid
sequenceDiagram
    participant C as Client (Browser)
    participant CF as Cloudflare Edge
    participant T as cloudflared (Tunnel)
    participant NX as Nginx (localhost:8081)
    participant G as Gunicorn/Uvicorn (localhost:8080)
    participant App as FastAPI + NiceGUI

    C->>CF: HTTPS request (www.pawsledger.com)
    CF->>CF: SSL termination + DDoS protection
    CF->>T: Encrypted tunnel connection
    T->>NX: HTTP request (localhost:8081)
    NX->>G: Proxy pass (localhost:8080)
    NX->>NX: Add WebSocket headers (Upgrade, Connection)
    G->>App: ASGI request
    App-->>G: Response (HTML + WebSocket upgrade)
    G-->>NX: Response
    NX-->>T: Response
    T-->>CF: Response
    CF-->>C: HTTPS response

    Note over C,App: WebSocket established for NiceGUI real-time UI
    C->>CF: WebSocket frames
    CF->>T: WebSocket relay
    T->>NX: WebSocket proxy
    NX->>G: WebSocket to Uvicorn
    G->>App: NiceGUI UI updates
    App-->>C: UI element changes (via WebSocket)
```
