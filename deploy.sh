#!/usr/bin/env bash
#
# PawsLedger — Hetzner VPS Deployment Script
# Deploys the application with Nginx + Gunicorn (Uvicorn workers) as user 'paws'.
#
# Stack:
#   - Nginx (reverse proxy + SSL termination)
#   - Gunicorn with Uvicorn workers (ASGI server)
#   - Python 3.11+ virtual environment
#   - SQLite database
#   - Let's Encrypt SSL via Certbot
#
# Usage:
#   1. SSH into your Hetzner VPS as root
#   2. Upload or clone the project to /tmp/paws-ledger (or any temp location)
#   3. Run: sudo bash deploy.sh
#
# Prerequisites:
#   - Debian/Ubuntu-based VPS (Hetzner Cloud with Ubuntu 22.04+ recommended)
#   - Root or sudo access
#   - A domain name pointed to the VPS IP (for SSL)
#   - Internet connectivity
#
# IMPORTANT: NiceGUI requires WebSocket support. This script configures Nginx
# to proxy WebSocket connections correctly. Gunicorn uses Uvicorn workers
# (UvicornWorker) since the app is ASGI-based (FastAPI + NiceGUI).

set -euo pipefail

# ─── Configuration ───────────────────────────────────────────
APP_USER="paws"
APP_DIR="/home/${APP_USER}/paws-ledger"
DATA_DIR="${APP_DIR}/data"
VENV_DIR="${APP_DIR}/.venv"
SERVICE_NAME="pawsledger"
APP_PORT=8080
WORKERS=2  # Uvicorn workers (NiceGUI works best with few workers due to WebSocket state)

# ─── Colors ──────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
step()  { echo -e "\n${CYAN}═══ $1 ═══${NC}"; }

# ─── Pre-flight checks ──────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    error "This script must be run as root (use sudo)."
fi

info "Starting PawsLedger deployment on Hetzner VPS..."
echo ""
read -rp "Enter your domain name (e.g. paws.example.com): " DOMAIN
if [[ -z "${DOMAIN}" ]]; then
    warn "No domain provided. Nginx will be configured with server IP only (no SSL)."
    DOMAIN="_"
    ENABLE_SSL=false
else
    ENABLE_SSL=true
fi

# ─────────────────────────────────────────────────────────────
step "Step 1: System Updates & Dependencies"
# ─────────────────────────────────────────────────────────────
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq \
    python3 python3-venv python3-pip python3-dev \
    nginx certbot python3-certbot-nginx \
    ufw curl git rsync build-essential \
    sqlite3

info "System packages installed."

# ─────────────────────────────────────────────────────────────
step "Step 2: Firewall (UFW)"
# ─────────────────────────────────────────────────────────────
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
info "Firewall configured: SSH + Nginx (HTTP/HTTPS) allowed."

# ─────────────────────────────────────────────────────────────
step "Step 3: Create Application User"
# ─────────────────────────────────────────────────────────────
if ! id "${APP_USER}" &> /dev/null; then
    adduser --disabled-password --gecos "PawsLedger Service" "${APP_USER}"
    info "User '${APP_USER}' created."
else
    info "User '${APP_USER}' already exists."
fi

# ─────────────────────────────────────────────────────────────
step "Step 4: Deploy Application Files"
# ─────────────────────────────────────────────────────────────
mkdir -p "${APP_DIR}"
mkdir -p "${DATA_DIR}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

info "Copying project files to ${APP_DIR}..."
rsync -a --exclude='.venv' \
         --exclude='.git' \
         --exclude='__pycache__' \
         --exclude='.pytest_cache' \
         --exclude='*.pyc' \
         --exclude='.DS_Store' \
         --exclude='pawsledger.db' \
         --exclude='data/' \
         --exclude='node_modules' \
         "${SCRIPT_DIR}/" "${APP_DIR}/"

chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"
chmod 755 "${DATA_DIR}"
info "Files deployed."

# ─────────────────────────────────────────────────────────────
step "Step 5: Python Virtual Environment & Dependencies"
# ─────────────────────────────────────────────────────────────
sudo -u "${APP_USER}" python3 -m venv "${VENV_DIR}"
sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install --upgrade pip wheel
sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install -r "${APP_DIR}/requirements.txt"
sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install gunicorn uvicorn[standard]
info "Python dependencies installed."

# ─────────────────────────────────────────────────────────────
step "Step 6: Environment Configuration"
# ─────────────────────────────────────────────────────────────
ENV_FILE="${APP_DIR}/.env"

if [[ -f "${ENV_FILE}" ]]; then
    warn ".env file already exists."
    read -rp "Overwrite? (y/N): " overwrite
    if [[ "${overwrite}" != "y" && "${overwrite}" != "Y" ]]; then
        info "Keeping existing .env file."
    else
        rm -f "${ENV_FILE}"
    fi
fi

if [[ ! -f "${ENV_FILE}" ]]; then
    STORAGE_SECRET=$(openssl rand -hex 32)

    echo ""
    echo "─── OAuth Configuration ───"
    echo "Leave blank to skip (edit ${ENV_FILE} later)."
    echo ""

    read -rp "Google Client ID: " GOOGLE_CLIENT_ID
    read -rp "Google Client Secret: " GOOGLE_CLIENT_SECRET

    if [[ "${DOMAIN}" != "_" ]]; then
        DEFAULT_CALLBACK="https://${DOMAIN}/api/v1/auth/callback"
    else
        DEFAULT_CALLBACK="http://$(hostname -I | awk '{print $1}'):${APP_PORT}/api/v1/auth/callback"
    fi
    read -rp "Google Callback URL [${DEFAULT_CALLBACK}]: " GOOGLE_CALLBACK_URL
    GOOGLE_CALLBACK_URL="${GOOGLE_CALLBACK_URL:-${DEFAULT_CALLBACK}}"

    cat > "${ENV_FILE}" <<EOF
# PawsLedger Environment Configuration
# Generated on $(date -u +"%Y-%m-%d %H:%M:%S UTC")

# Application
APP_ENV=prod
DATABASE_URL=sqlite:///${DATA_DIR}/pawsledger.db
STORAGE_SECRET=${STORAGE_SECRET}

# Google OAuth
GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}
GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}
GOOGLE_CALLBACK_URL=${GOOGLE_CALLBACK_URL}
EOF

    chown "${APP_USER}:${APP_USER}" "${ENV_FILE}"
    chmod 600 "${ENV_FILE}"
    info ".env file created."
fi

# ─────────────────────────────────────────────────────────────
step "Step 7: Gunicorn Systemd Service"
# ─────────────────────────────────────────────────────────────
cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF
[Unit]
Description=PawsLedger Gunicorn ASGI Server
After=network.target

[Service]
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_DIR}/bin/gunicorn app.main:fastapi_app \\
    --worker-class uvicorn.workers.UvicornWorker \\
    --workers ${WORKERS} \\
    --bind 127.0.0.1:${APP_PORT} \\
    --timeout 120 \\
    --graceful-timeout 30 \\
    --keep-alive 65 \\
    --access-logfile /var/log/${SERVICE_NAME}/access.log \\
    --error-logfile /var/log/${SERVICE_NAME}/error.log
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Create log directory
mkdir -p "/var/log/${SERVICE_NAME}"
chown "${APP_USER}:${APP_USER}" "/var/log/${SERVICE_NAME}"

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"
info "Systemd service '${SERVICE_NAME}' created and enabled."

# ─────────────────────────────────────────────────────────────
step "Step 8: Nginx Configuration"
# ─────────────────────────────────────────────────────────────

# Remove default site
rm -f /etc/nginx/sites-enabled/default

cat > "/etc/nginx/sites-available/${SERVICE_NAME}" <<EOF
# PawsLedger Nginx Configuration
# Reverse proxy to Gunicorn with WebSocket support for NiceGUI

upstream pawsledger_backend {
    server 127.0.0.1:${APP_PORT};
}

server {
    listen 80;
    server_name ${DOMAIN};

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Max upload size (for pet photos etc.)
    client_max_body_size 10M;

    # Proxy all requests to Gunicorn
    location / {
        proxy_pass http://pawsledger_backend;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # WebSocket support (required for NiceGUI)
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }

    # NiceGUI socket.io endpoint (explicit WebSocket handling)
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

    # Static files (served directly by Nginx for performance)
    location /static/ {
        alias ${APP_DIR}/app/ui/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # Health check endpoint
    location /health {
        proxy_pass http://pawsledger_backend/docs;
        access_log off;
    }
}
EOF

ln -sf "/etc/nginx/sites-available/${SERVICE_NAME}" "/etc/nginx/sites-enabled/${SERVICE_NAME}"

# Test Nginx config
nginx -t
info "Nginx configured with WebSocket proxy support."

# ─────────────────────────────────────────────────────────────
step "Step 9: Start Services"
# ─────────────────────────────────────────────────────────────
systemctl restart "${SERVICE_NAME}"
systemctl restart nginx
info "Gunicorn and Nginx started."

# ─────────────────────────────────────────────────────────────
step "Step 10: SSL Certificate (Let's Encrypt)"
# ─────────────────────────────────────────────────────────────
if [[ "${ENABLE_SSL}" == true ]]; then
    echo ""
    read -rp "Set up SSL with Let's Encrypt now? (Y/n): " setup_ssl
    if [[ "${setup_ssl}" != "n" && "${setup_ssl}" != "N" ]]; then
        read -rp "Email for Let's Encrypt notifications: " LE_EMAIL
        certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos --email "${LE_EMAIL}" --redirect
        info "SSL certificate installed. HTTPS enabled with auto-redirect."

        # Certbot auto-renewal is set up automatically via systemd timer
        systemctl enable certbot.timer
        systemctl start certbot.timer
    else
        warn "Skipping SSL. Run manually later:"
        echo "  sudo certbot --nginx -d ${DOMAIN}"
    fi
else
    warn "No domain configured — skipping SSL setup."
    echo "  To add SSL later, configure your domain and run:"
    echo "  sudo certbot --nginx -d your-domain.com"
fi

# ─────────────────────────────────────────────────────────────
step "Step 11: Verify Deployment"
# ─────────────────────────────────────────────────────────────
sleep 3

if systemctl is-active --quiet "${SERVICE_NAME}"; then
    info "Gunicorn service is running."
else
    warn "Gunicorn service may not be running. Check:"
    echo "  sudo systemctl status ${SERVICE_NAME}"
    echo "  sudo journalctl -u ${SERVICE_NAME} -n 50"
fi

if systemctl is-active --quiet nginx; then
    info "Nginx is running."
else
    warn "Nginx may not be running. Check:"
    echo "  sudo systemctl status nginx"
fi

# ─── Summary ─────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
info "PawsLedger deployment complete!"
echo ""
echo "  Domain:         ${DOMAIN}"
echo "  App directory:  ${APP_DIR}"
echo "  Data directory: ${DATA_DIR}"
echo "  Config file:    ${ENV_FILE}"
echo "  Logs:           /var/log/${SERVICE_NAME}/"
echo ""
echo "  ┌─────────────────────────────────────────────────────────┐"
echo "  │  Architecture:                                          │"
echo "  │                                                         │"
echo "  │  Client → Nginx (443/80) → Gunicorn (8080) → FastAPI   │"
echo "  │              ↕ WebSocket      ↕ Uvicorn Workers          │"
echo "  │              SSL              NiceGUI UI                 │"
echo "  └─────────────────────────────────────────────────────────┘"
echo ""
echo "  Useful commands:"
echo "    sudo systemctl status ${SERVICE_NAME}    # App status"
echo "    sudo systemctl restart ${SERVICE_NAME}   # Restart app"
echo "    sudo journalctl -u ${SERVICE_NAME} -f    # Live logs"
echo "    sudo tail -f /var/log/${SERVICE_NAME}/error.log"
echo "    sudo nginx -t                            # Test Nginx config"
echo "    sudo systemctl restart nginx             # Restart Nginx"
echo ""
echo "  Deployment as user '${APP_USER}':"
echo "    sudo su - ${APP_USER}"
echo "    cd ~/paws-ledger"
echo "    source .venv/bin/activate"
echo "    python -m app.main                       # Manual run (dev)"
echo ""
if [[ "${ENABLE_SSL}" == true ]]; then
    echo "  URL: https://${DOMAIN}"
else
    echo "  URL: http://$(hostname -I | awk '{print $1}')"
fi
echo "═══════════════════════════════════════════════════════════════"
