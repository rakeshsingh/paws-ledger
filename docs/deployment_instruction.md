# PawsLedger — Deployment Guide

## Table of Contents

- [Local Development](#local-development)
- [Production Deployment (Hetzner VPS + Cloudflare Tunnel)](#production-deployment)
- [Updating the Application](#updating-the-application)
- [Maintenance & Troubleshooting](#maintenance--troubleshooting)

---

## Local Development

### Prerequisites

- Python 3.11 or higher
- `uv` package manager (recommended) or `pip`
- Git

### Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd paws-ledger
   ```

2. **Create a virtual environment and install dependencies:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate        # Linux/macOS
   # .venv\Scripts\activate         # Windows
   pip install -r requirements.txt
   ```

   Or with `uv`:
   ```bash
   uv venv .venv
   uv pip install -r requirements.txt
   ```

3. **Configure environment:**

   The `.env.beta` file exists with defaults. For Google OAuth to work locally, set:
   ```
   GOOGLE_CLIENT_ID=your_client_id
   GOOGLE_CLIENT_SECRET=your_secret
   GOOGLE_CALLBACK_URL=http://localhost:8080/api/v1/auth/callback
   ```

   Also register `http://localhost:8080/api/v1/auth/callback` in your Google Cloud Console under Authorized redirect URIs.

4. **Seed the database (optional):**
   ```bash
   python seed_db.py
   ```

### Running Locally

```bash
python -m app.main
```

The app starts on `http://localhost:8080`:
- **UI:** http://localhost:8080
- **API docs (Swagger):** http://localhost:8080/docs
- **API docs (ReDoc):** http://localhost:8080/redoc

### Running with Auto-Reload (Development)

```bash
uvicorn app.main:fastapi_app --host 0.0.0.0 --port 8080 --reload
```

### Running Tests

```bash
python -m pytest tests/ -v
```

---

## Production Deployment

### Architecture

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
│  Nginx (127.0.0.1:8081)     │  ← WebSocket proxy, static files
└──────────────┬───────────────┘
               │ HTTP (localhost:8080)
               ▼
┌──────────────────────────────┐
│  Gunicorn (127.0.0.1:8080)  │  ← ASGI server, 1 Uvicorn worker
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│  FastAPI + NiceGUI App       │  ← Application logic
│  SQLite (WAL mode)           │  ← Persistent storage
└──────────────────────────────┘
```

### Important Notes

- **1 Gunicorn worker required.** NiceGUI maintains WebSocket state per-process. Multiple workers cause blank pages due to session affinity issues.
- **Nginx must proxy WebSocket connections** (`Upgrade` and `Connection` headers) with long timeouts (86400s).
- **Cloudflare Tunnel** handles SSL — no certificates on the VPS, no open HTTP/HTTPS ports.
- **Gunicorn uses `UvicornWorker`** because the app is ASGI-based (FastAPI + NiceGUI).

### Prerequisites

- Hetzner Cloud VPS (CX21 or higher — 2 vCPU, 4GB RAM)
- Ubuntu 22.04 LTS or Debian 12
- A domain hosted on Cloudflare
- A Cloudflare Tunnel token (Zero Trust → Networks → Tunnels)
- SSH access as root

### Quick Deploy

```bash
# 1. SSH into your VPS
ssh root@your-vps-ip

# 2. Clone the project
git clone <repository-url> /tmp/paws-ledger
cd /tmp/paws-ledger

# 3. Run the deploy script
sudo bash deploy.sh
```

The script prompts for:
- Domain name (e.g. `www.pawsledger.com`)
- Google OAuth credentials
- Cloudflare Tunnel token

### What the Deploy Script Does

| Step | Action |
|------|--------|
| 1 | Updates system packages, installs Python 3, Nginx, UFW |
| 2 | Installs `cloudflared` from official release |
| 3 | Configures firewall (SSH only — no HTTP/HTTPS ports needed) |
| 4 | Creates the `paws` system user |
| 5 | Copies project files to `/home/paws/paws-ledger` |
| 6 | Creates Python venv, installs dependencies + Gunicorn |
| 7 | Generates `.env` with secrets and OAuth config |
| 8 | Creates systemd service for Gunicorn (1 worker, auto-start) |
| 9 | Configures Nginx with WebSocket proxy (localhost:8081) |
| 10 | Installs Cloudflare Tunnel service with token |
| 11 | Starts all services and verifies |

### Cloudflare Tunnel Configuration

In the Cloudflare Zero Trust dashboard (Networks → Tunnels → your tunnel → Public Hostname):

| Field | Value |
|-------|-------|
| Subdomain | `www` (or blank for apex) |
| Domain | `pawsledger.com` |
| Type | `HTTP` |
| URL | `localhost:8081` |

DNS records (auto-created or add manually):
- `www` CNAME → `<tunnel-id>.cfargotunnel.com` (Proxied)
- `@` CNAME → `<tunnel-id>.cfargotunnel.com` (Proxied)

Ensure **WebSockets** is enabled: Cloudflare dashboard → Network → WebSockets ON.

### Environment Variables (Production)

| Variable | Description |
|----------|-------------|
| `APP_ENV` | `prod` |
| `DATABASE_URL` | `sqlite:////home/paws/paws-ledger/data/pawsledger.db` |
| `STORAGE_SECRET` | Random 64-char hex (generated by deploy script) |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret |
| `GOOGLE_CALLBACK_URL` | `https://www.pawsledger.com/api/v1/auth/callback` |
| `RESEND_API_KEY` | Resend.com API key (for email notifications) |
| `EMAIL_FROM` | `PawsLedger <alerts@pawsledger.com>` |
| `GA_MEASUREMENT_ID` | Google Analytics ID (default: `G-VQSSWXZFKL`) |
| `BASE_URL` | `https://www.pawsledger.com` |

### Manual Setup (Step by Step)

#### 1. System Dependencies

```bash
apt update && apt upgrade -y
apt install -y python3 python3-venv python3-pip nginx ufw curl sqlite3
curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
dpkg -i /tmp/cloudflared.deb
```

#### 2. Firewall

```bash
ufw allow OpenSSH
ufw --force enable
# No HTTP/HTTPS ports needed — Cloudflare Tunnel connects outbound
```

#### 3. Application User

```bash
adduser --disabled-password --gecos "PawsLedger" paws
```

#### 4. Deploy Files

```bash
mkdir -p /home/paws/paws-ledger/data
rsync -a --exclude='.venv' --exclude='.git' --exclude='__pycache__' ./ /home/paws/paws-ledger/
chown -R paws:paws /home/paws/paws-ledger
```

#### 5. Python Environment

```bash
sudo -u paws python3 -m venv /home/paws/paws-ledger/.venv
sudo -u paws /home/paws/paws-ledger/.venv/bin/pip install -r /home/paws/paws-ledger/requirements.txt
sudo -u paws /home/paws/paws-ledger/.venv/bin/pip install gunicorn uvicorn[standard]
```

#### 6. Environment File

```bash
cat > /home/paws/paws-ledger/.env <<EOF
APP_ENV=prod
DATABASE_URL=sqlite:////home/paws/paws-ledger/data/pawsledger.db
STORAGE_SECRET=$(openssl rand -hex 32)
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_secret
GOOGLE_CALLBACK_URL=https://www.pawsledger.com/api/v1/auth/callback
RESEND_API_KEY=re_your_key
EMAIL_FROM=PawsLedger <alerts@pawsledger.com>
BASE_URL=https://www.pawsledger.com
EOF
chmod 600 /home/paws/paws-ledger/.env
chown paws:paws /home/paws/paws-ledger/.env
```

#### 7. Systemd Service

```bash
cat > /etc/systemd/system/pawsledger.service <<EOF
[Unit]
Description=PawsLedger Gunicorn ASGI Server
After=network.target

[Service]
User=paws
Group=paws
WorkingDirectory=/home/paws/paws-ledger
EnvironmentFile=/home/paws/paws-ledger/.env
ExecStart=/home/paws/paws-ledger/.venv/bin/gunicorn app.main:fastapi_app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 1 \
    --bind 127.0.0.1:8080 \
    --timeout 120 \
    --graceful-timeout 30 \
    --keep-alive 65 \
    --forwarded-allow-ips="127.0.0.1" \
    --access-logfile /var/log/pawsledger/access.log \
    --error-logfile /var/log/pawsledger/error.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

mkdir -p /var/log/pawsledger
chown paws:paws /var/log/pawsledger
systemctl daemon-reload
systemctl enable pawsledger
systemctl start pawsledger
```

#### 8. Nginx Configuration

```bash
cat > /etc/nginx/sites-available/pawsledger <<'EOF'
upstream pawsledger_backend {
    server 127.0.0.1:8080;
}

server {
    listen 127.0.0.1:8081;
    server_name www.pawsledger.com pawsledger.com;

    client_max_body_size 10M;

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    location / {
        proxy_pass http://pawsledger_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }

    location /_nicegui_ws/ {
        proxy_pass http://pawsledger_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }

    location /static/ {
        alias /home/paws/paws-ledger/app/ui/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }
}
EOF

ln -sf /etc/nginx/sites-available/pawsledger /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx
```

#### 9. Cloudflare Tunnel

```bash
cloudflared service install <YOUR_TUNNEL_TOKEN>
```

---

## Updating the Application

```bash
cd /home/paws/paws-ledger
sudo -u paws git pull
sudo -u paws .venv/bin/pip install -r requirements.txt
sudo systemctl restart pawsledger
```

---

## Maintenance & Troubleshooting

### View Logs

```bash
sudo journalctl -u pawsledger -f              # App logs (live)
sudo tail -f /var/log/pawsledger/error.log    # Gunicorn errors
sudo tail -f /var/log/pawsledger/access.log   # HTTP access
sudo tail -f /var/log/nginx/error.log         # Nginx errors
sudo journalctl -u cloudflared -f             # Tunnel logs
```

### Service Management

```bash
sudo systemctl status pawsledger      # App status
sudo systemctl restart pawsledger     # Restart app
sudo systemctl status cloudflared     # Tunnel status
sudo systemctl status nginx           # Nginx status
sudo nginx -t                         # Test Nginx config
```

### Database Backup

```bash
sudo -u paws sqlite3 /home/paws/paws-ledger/data/pawsledger.db \
  ".backup '/home/paws/paws-ledger/data/backup-$(date +%Y%m%d).db'"
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| 502 Bad Gateway | `sudo systemctl status pawsledger` — check if app is running |
| 521 Cloudflare error | DNS not pointing to tunnel. Check CNAME records point to `<tunnel-id>.cfargotunnel.com` |
| Blank page in browser | Clear site cookies/localStorage, or wait 3s for auto-reload |
| WebSocket errors | Verify Nginx has `Upgrade` + `Connection` headers + 86400s timeout |
| "No module named X" | `sudo -u paws .venv/bin/pip install -r requirements.txt` |
| OAuth state mismatch | Use incognito window. The fallback token exchange handles this. |
| Permission denied on DB | `sudo chown paws:paws /home/paws/paws-ledger/data/pawsledger.db` |
| App crash loop | `sudo journalctl -u pawsledger -n 50` for the Python error |
| Multiple workers blank page | Ensure `--workers 1` in systemd service file |

### Security Checklist

- [x] Firewall — SSH only (no HTTP/HTTPS ports open)
- [x] App runs as unprivileged user (`paws`)
- [x] `.env` file has `chmod 600`
- [x] SSL via Cloudflare (no certs on VPS)
- [x] Nginx binds to `127.0.0.1` only
- [x] Gunicorn binds to `127.0.0.1` only
- [x] Rate limiting on auth/lookup/nudge endpoints
- [x] Ownership verification on all pet mutation APIs
- [x] Signed session cookies with strong secret
- [x] No PII in logs
