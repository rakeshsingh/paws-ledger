# PawsLedger — Hetzner VPS Deployment Guide

Deploy PawsLedger on a Hetzner Cloud VPS using Nginx as a reverse proxy and Gunicorn with Uvicorn workers as the ASGI application server.

## Architecture

```
Client (Browser)
    │
    ▼
┌─────────────────────────┐
│  Nginx (port 80/443)    │  ← SSL termination, static files, WebSocket proxy
│  Reverse Proxy          │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  Gunicorn (port 8080)   │  ← ASGI server with UvicornWorker class
│  2 Uvicorn Workers      │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  FastAPI + NiceGUI      │  ← Application (API + UI)
│  SQLite Database        │
└─────────────────────────┘
```

## Important Notes

- **NiceGUI requires WebSocket support.** Nginx must be configured to proxy WebSocket connections (`Upgrade` and `Connection` headers). The deploy script handles this.
- **Gunicorn must use Uvicorn workers** (`uvicorn.workers.UvicornWorker`) because the app is ASGI-based (FastAPI + NiceGUI). Standard sync workers will not work.
- **Worker count should be low** (2-3). NiceGUI maintains WebSocket state per connection, so too many workers can cause session issues. For a single-server deployment, 2 workers is recommended.

## Prerequisites

- Hetzner Cloud VPS (CX21 or higher recommended — 2 vCPU, 4GB RAM)
- Ubuntu 22.04 LTS or Debian 12
- A domain name with DNS A record pointing to the VPS IP
- SSH access as root

## Quick Deploy

```bash
# 1. SSH into your VPS
ssh root@your-vps-ip

# 2. Clone or upload the project
git clone <repository-url> /tmp/paws-ledger
cd /tmp/paws-ledger

# 3. Run the deploy script
sudo bash deploy.sh
```

The script will prompt you for:
- Your domain name (for Nginx + SSL)
- Google OAuth credentials (Client ID, Secret, Callback URL)
- Whether to set up Let's Encrypt SSL

## What the Deploy Script Does

| Step | Action |
|------|--------|
| 1 | Updates system packages, installs Python 3, Nginx, Certbot, UFW |
| 2 | Configures firewall (SSH + HTTP/HTTPS only) |
| 3 | Creates the `paws` system user |
| 4 | Copies project files to `/home/paws/paws-ledger` |
| 5 | Creates Python venv, installs dependencies + Gunicorn |
| 6 | Generates `.env` with secrets and OAuth config |
| 7 | Creates systemd service for Gunicorn (auto-start on boot) |
| 8 | Configures Nginx with WebSocket proxy support |
| 9 | Starts Gunicorn and Nginx |
| 10 | Optionally installs Let's Encrypt SSL certificate |
| 11 | Verifies services are running |

## Manual Setup (Step by Step)

If you prefer to set things up manually instead of using the script:

### 1. Install System Dependencies

```bash
apt update && apt upgrade -y
apt install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx ufw curl sqlite3
```

### 2. Configure Firewall

```bash
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
```

### 3. Create Application User

```bash
adduser --disabled-password --gecos "PawsLedger" paws
```

### 4. Deploy Application

```bash
mkdir -p /home/paws/paws-ledger/data
# Copy project files to /home/paws/paws-ledger
chown -R paws:paws /home/paws/paws-ledger
```

### 5. Install Python Dependencies

```bash
sudo -u paws python3 -m venv /home/paws/paws-ledger/.venv
sudo -u paws /home/paws/paws-ledger/.venv/bin/pip install -r /home/paws/paws-ledger/requirements.txt
sudo -u paws /home/paws/paws-ledger/.venv/bin/pip install gunicorn uvicorn[standard]
```

### 6. Create .env File

```bash
cat > /home/paws/paws-ledger/.env <<EOF
APP_ENV=prod
DATABASE_URL=sqlite:////home/paws/paws-ledger/data/pawsledger.db
STORAGE_SECRET=$(openssl rand -hex 32)
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_secret
GOOGLE_CALLBACK_URL=https://your-domain.com/api/v1/auth/callback
EOF
chmod 600 /home/paws/paws-ledger/.env
chown paws:paws /home/paws/paws-ledger/.env
```

### 7. Create Systemd Service

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
    --workers 2 \
    --bind 127.0.0.1:8080 \
    --timeout 120 \
    --graceful-timeout 30 \
    --keep-alive 65 \
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

### 8. Configure Nginx

```bash
cat > /etc/nginx/sites-available/pawsledger <<EOF
upstream pawsledger_backend {
    server 127.0.0.1:8080;
}

server {
    listen 80;
    server_name your-domain.com;

    client_max_body_size 10M;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    location / {
        proxy_pass http://pawsledger_backend;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # WebSocket support (REQUIRED for NiceGUI)
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }

    # NiceGUI WebSocket endpoint
    location /_nicegui_ws/ {
        proxy_pass http://pawsledger_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }

    # Static files
    location /static/ {
        alias /home/paws/paws-ledger/app/ui/static/;
        expires 7d;
    }
}
EOF

ln -sf /etc/nginx/sites-available/pawsledger /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx
```

### 9. SSL with Let's Encrypt

```bash
certbot --nginx -d your-domain.com --agree-tos --email you@example.com --redirect
```

## Maintenance

### View Logs

```bash
# Application logs
sudo journalctl -u pawsledger -f
sudo tail -f /var/log/pawsledger/error.log
sudo tail -f /var/log/pawsledger/access.log

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Restart Services

```bash
sudo systemctl restart pawsledger   # Restart app
sudo systemctl restart nginx        # Restart Nginx
```

### Update Application

```bash
cd /home/paws/paws-ledger
sudo -u paws git pull  # or rsync new files
sudo -u paws .venv/bin/pip install -r requirements.txt
sudo systemctl restart pawsledger
```

### Database Backup

```bash
# SQLite backup (safe while app is running)
sudo -u paws sqlite3 /home/paws/paws-ledger/data/pawsledger.db ".backup '/home/paws/backups/pawsledger-$(date +%Y%m%d).db'"
```

### SSL Certificate Renewal

Certbot sets up automatic renewal via systemd timer. To test:

```bash
sudo certbot renew --dry-run
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| 502 Bad Gateway | Check if Gunicorn is running: `systemctl status pawsledger` |
| WebSocket errors in browser | Verify Nginx has `proxy_set_header Upgrade` and `Connection "upgrade"` |
| NiceGUI pages blank | Ensure `proxy_read_timeout 86400` is set (WebSocket needs long timeout) |
| Permission denied on DB | `chown paws:paws /home/paws/paws-ledger/data/pawsledger.db` |
| SSL not working | Run `certbot --nginx -d your-domain.com` and check DNS A record |
| App won't start | Check `journalctl -u pawsledger -n 50` for Python errors |

## Security Checklist

- [x] Firewall (UFW) — only SSH, HTTP, HTTPS open
- [x] App runs as unprivileged user (`paws`)
- [x] `.env` file has `chmod 600` (owner-only read)
- [x] Nginx security headers (X-Frame-Options, X-Content-Type-Options)
- [x] SSL/TLS via Let's Encrypt with auto-redirect
- [x] Gunicorn binds to `127.0.0.1` only (not exposed to internet directly)
- [x] SQLite database in dedicated data directory with restricted permissions
