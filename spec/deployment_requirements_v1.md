# Deployment Requirements — v1

## Overview

PawsLedger is deployed on a Hetzner Cloud VPS using a secure, zero-open-port architecture with Cloudflare Tunnel for SSL termination and ingress routing.

## Target Environment

| Component | Specification |
|-----------|--------------|
| Provider | Hetzner Cloud |
| Instance | CX21 or higher (2 vCPU, 4GB RAM minimum) |
| OS | Ubuntu 22.04 LTS or Debian 12 |
| DNS/SSL | Cloudflare (domain hosted on Cloudflare) |
| Ingress | Cloudflare Tunnel (Zero Trust) |

## Architecture

```
Client (Browser)
    │ HTTPS
    ▼
┌──────────────────────────────┐
│  Cloudflare Edge (SSL/CDN)   │  ← SSL termination, DDoS protection
└──────────────┬───────────────┘
               │ Encrypted tunnel (outbound from VPS)
               ▼
┌──────────────────────────────┐
│  cloudflared (tunnel daemon) │  ← Runs on VPS, connects outbound to Cloudflare
└──────────────┬───────────────┘
               │ HTTP (localhost:8081)
               ▼
┌──────────────────────────────┐
│  Nginx (127.0.0.1:8081)     │  ← WebSocket proxy, static files, request buffering
└──────────────┬───────────────┘
               │ HTTP (localhost:8080)
               ▼
┌──────────────────────────────┐
│  Gunicorn (127.0.0.1:8080)  │  ← ASGI server with UvicornWorker
│  2 Uvicorn Workers           │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│  FastAPI + NiceGUI App       │  ← Application logic
│  SQLite Database             │  ← Persistent storage in /data
└──────────────────────────────┘
```

## Security Requirements

1. **No public HTTP/HTTPS ports** — The VPS firewall (UFW) only allows SSH. All web traffic flows through the Cloudflare Tunnel which connects outbound.
2. **SSL handled by Cloudflare** — No certificates stored on the VPS. Cloudflare provides edge SSL with automatic renewal.
3. **Application runs as unprivileged user** — The `paws` system user owns all application files and runs Gunicorn. No root access needed at runtime.
4. **Environment secrets protected** — The `.env` file has `chmod 600` (owner-only read). Contains OAuth secrets and the storage signing key.
5. **Nginx binds to localhost only** — `127.0.0.1:8081`, not exposed to the network.
6. **Gunicorn binds to localhost only** — `127.0.0.1:8080`, not exposed to the network.
7. **Security headers** — Nginx adds X-Frame-Options, X-Content-Type-Options, X-XSS-Protection, and Referrer-Policy headers.

## Component Requirements

### Cloudflare Tunnel

- **Package**: `cloudflared` (latest stable `.deb` from GitHub releases)
- **Service**: Installed as a systemd service via `cloudflared service install <TOKEN>`
- **Dashboard config**:
  - Public Hostname: `<domain>` (e.g. `paws.example.com`)
  - Service Type: `HTTP`
  - Service URL: `localhost:8081`
- **WebSocket support**: Native in Cloudflare Tunnels — no additional config needed

### Nginx

- **Role**: Local reverse proxy between cloudflared and Gunicorn
- **Binding**: `127.0.0.1:8081`
- **Responsibilities**:
  - WebSocket upgrade headers (`Upgrade`, `Connection`) for NiceGUI
  - Long read/send timeouts (86400s) for persistent WebSocket connections
  - Static file serving from `app/ui/static/` with 7-day cache
  - `X-Forwarded-Proto: https` header injection (since SSL terminates at Cloudflare)
  - Request body size limit: 10MB
- **Dedicated NiceGUI WebSocket location**: `/_nicegui_ws/` with explicit WebSocket proxy config

### Gunicorn

- **Worker class**: `uvicorn.workers.UvicornWorker` (required — app is ASGI)
- **Workers**: 2 (NiceGUI maintains WebSocket state per connection; more workers can cause session issues)
- **Binding**: `127.0.0.1:8080`
- **Timeouts**: 120s request timeout, 30s graceful shutdown, 65s keep-alive
- **Logging**: Access and error logs to `/var/log/pawsledger/`

### Python Environment

- **Version**: Python 3.11+
- **Virtual environment**: `/home/paws/paws-ledger/.venv`
- **Dependencies**: Installed from `requirements.txt` plus `gunicorn` and `uvicorn[standard]`
- **No system-wide pip installs** — everything in the venv

### SQLite Database

- **Location**: `/home/paws/paws-ledger/data/pawsledger.db`
- **Ownership**: `paws:paws`
- **Backup strategy**: `sqlite3 .backup` command (safe while app is running)

## Process Management

All services are managed via systemd:

| Service | Unit Name | Auto-start |
|---------|-----------|------------|
| Application (Gunicorn) | `pawsledger.service` | Yes (WantedBy=multi-user.target) |
| Tunnel (cloudflared) | `cloudflared.service` | Yes (installed by cloudflared) |
| Reverse Proxy (Nginx) | `nginx.service` | Yes (default) |

### Service Dependencies

- `pawsledger.service` starts after `network.target`
- `cloudflared.service` starts after `network-online.target`
- Nginx has no explicit dependency on the app (proxies to localhost, returns 502 if app is down)

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `APP_ENV` | Environment name (`prod`) | Yes |
| `DATABASE_URL` | SQLite connection string | Yes |
| `STORAGE_SECRET` | Signing key for session cookies (hex, 64 chars) | Yes |
| `GOOGLE_CLIENT_ID` | Google OAuth 2.0 client ID | Yes |
| `GOOGLE_CLIENT_SECRET` | Google OAuth 2.0 client secret | Yes |
| `GOOGLE_CALLBACK_URL` | OAuth redirect URI (must match Google Console) | Yes |

## Deployment Process

The `deploy.sh` script automates the full deployment:

1. System update and dependency installation
2. `cloudflared` installation from official release
3. Firewall lockdown (SSH only)
4. Application user creation (`paws`)
5. Project file deployment via rsync
6. Python venv creation and dependency installation
7. `.env` file generation with prompted secrets
8. Gunicorn systemd service creation
9. Nginx configuration with WebSocket proxy
10. Cloudflare Tunnel service installation
11. Service startup and verification

### Update Process

```bash
# As root or with sudo:
cd /home/paws/paws-ledger
sudo -u paws rsync -a --exclude='.venv' --exclude='data/' <source>/ ./
sudo -u paws .venv/bin/pip install -r requirements.txt
sudo systemctl restart pawsledger
```

## Monitoring & Observability

| What | How |
|------|-----|
| App logs | `journalctl -u pawsledger -f` or `/var/log/pawsledger/error.log` |
| Tunnel status | `journalctl -u cloudflared -f` |
| Nginx logs | `/var/log/nginx/access.log` and `error.log` |
| Service health | `systemctl status pawsledger nginx cloudflared` |
| Tunnel connectivity | Cloudflare Zero Trust dashboard → Tunnels → Connectors |

## Constraints & Limitations

1. **Single server** — No horizontal scaling. NiceGUI WebSocket state is per-process, making multi-server deployment complex without sticky sessions.
2. **SQLite** — Single-writer limitation. Suitable for the current user scale but would need migration to PostgreSQL for high concurrency.
3. **2 workers** — Limited concurrent WebSocket connections. Each worker handles connections independently. Scale vertically (bigger VPS) if needed.
4. **No zero-downtime deploys** — Restarting Gunicorn briefly drops active WebSocket connections. Users will auto-reconnect via NiceGUI's built-in reconnection logic.

## Rollback Strategy

1. Keep the previous version's files in a timestamped backup before deploying
2. If the new version fails, restore files and restart:
   ```bash
   sudo -u paws cp -r /home/paws/paws-ledger /home/paws/paws-ledger.bak.$(date +%s)
   # ... deploy new version ...
   # If it fails:
   sudo systemctl stop pawsledger
   sudo -u paws rm -rf /home/paws/paws-ledger
   sudo -u paws mv /home/paws/paws-ledger.bak.<timestamp> /home/paws/paws-ledger
   sudo systemctl start pawsledger
   ```
3. Database is backward-compatible (additive schema changes only via ALTER TABLE)
