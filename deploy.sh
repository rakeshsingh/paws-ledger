#!/usr/bin/env bash
#
# PawsLedger — Hetzner VPS Deployment Script
# Deploys the application with Nginx + Gunicorn + Cloudflare Tunnel as user 'paws'.
#
# Stack:
#   - Cloudflare Tunnel (SSL termination + secure ingress, no open ports)
#   - Nginx (local reverse proxy + WebSocket handling + static files)
#   - Gunicorn with Uvicorn workers (ASGI server)
#   - Python 3.11+ virtual environment
#   - SQLite database
#
# Usage:
#   1. SSH into your Hetzner VPS as root
#   2. Upload or clone the project to /tmp/paws-ledger (or any temp location)
#   3. Run: sudo bash deploy.sh
#
# Prerequisites:
#   - Debian/Ubuntu-based VPS (Hetzner Cloud with Ubuntu 22.04+ recommended)
#   - Root or sudo access
#   - A Cloudflare account with a domain and a Tunnel token
#     (Create at: Zero Trust → Networks → Tunnels → Create Tunnel → Docker/CLI)
#   - Internet connectivity
#
# IMPORTANT: NiceGUI requires WebSocket support. Cloudflare Tunnels support
# WebSockets natively. Nginx is configured to proxy WebSocket connections
# between cloudflared and Gunicorn.

set -euo pipefail

# ─── Configuration ───────────────────────────────────────────
APP_USER="paws"
APP_DIR="/home/${APP_USER}/paws-ledger"
DATA_DIR="${APP_DIR}/data"
VENV_DIR="${APP_DIR}/.venv"
SERVICE_NAME="pawsledger"
APP_PORT=8080
NGINX_PORT=8081  # Nginx listens here; cloudflared points to this
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

info "Starting PawsLedger deployment on Hetzner VPS (Cloudflare Tunnel)..."
echo ""
read -rp "Enter your domain name (e.g. paws.example.com): " DOMAIN
if [[ -z "${DOMAIN}" ]]; then
    error "Domain is required for Cloudflare Tunnel configuration."
fi

# ─────────────────────────────────────────────────────────────
step "Step 1: System Updates & Dependencies"
# ─────────────────────────────────────────────────────────────
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq \
    python3 python3-venv python3-pip python3-dev \
    nginx curl git rsync build-essential sqlite3

info "System packages installed."

# ─────────────────────────────────────────────────────────────
step "Step 2: Install Cloudflare Tunnel (cloudflared)"
# ─────────────────────────────────────────────────────────────
if ! command -v cloudflared &> /dev/null; then
    info "Installing cloudflared..."
    curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
    dpkg -i /tmp/cloudflared.deb
    rm /tmp/cloudflared.deb
    info "cloudflared installed."
else
    info "cloudflared already installed ($(cloudflared --version))."
fi

# ─────────────────────────────────────────────────────────────
step "Step 3: Firewall (UFW) — Lockdown"
# ─────────────────────────────────────────────────────────────
apt-get install -y -qq ufw
ufw allow OpenSSH
# No HTTP/HTTPS ports needed — Cloudflare Tunnel connects outbound
ufw --force enable
info "Firewall configured: Only SSH allowed. No inbound HTTP/HTTPS ports needed."

# ─────────────────────────────────────────────────────────────
step "Step 4: Create Application User"
# ─────────────────────────────────────────────────────────────
if ! id "${APP_USER}" &> /dev/null; then
    adduser --disabled-password --gecos "PawsLedger Service" "${APP_USER}"
    info "User '${APP_USER}' created."
else
    info "User '${APP_USER}' already exists."
fi

# ─────────────────────────────────────────────────────────────
step "Step 5: Deploy Application Files"
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
step "Step 6: Python Virtual Environment & Dependencies"
# ─────────────────────────────────────────────────────────────
sudo -u "${APP_USER}" python3 -m venv "${VENV_DIR}"
sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install --upgrade pip wheel
sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install -r "${APP_DIR}/requirements.txt"
sudo -u "${APP_USER}" "${VENV_DIR}/bin/pip" install gunicorn uvicorn[standard]
info "Python dependencies installed."

# ─────────────────────────────────────────────────────────────
step "Step 7: Environment Configuration"
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
    DEFAULT_CALLBACK="https://${DOMAIN}/api/v1/auth/callback"
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
step "Step 8: Gunicorn Systemd Service"
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
    --forwarded-allow-ips="127.0.0.1" \\
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

mkdir -p "/var/log/${SERVICE_NAME}"
chown "${APP_USER}:${APP_USER}" "/var/log/${SERVICE_NAME}"

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}.service"
info "Gunicorn systemd service created and enabled."

# ─────────────────────────────────────────────────────────────
step "Step 9: Nginx Configuration (Local Reverse Proxy)"
# ─────────────────────────────────────────────────────────────
# Nginx sits between cloudflared and Gunicorn to handle:
# - WebSocket upgrade headers for NiceGUI
# - Static file serving
# - Request buffering

rm -f /etc/nginx/sites-enabled/default

cat > "/etc/nginx/sites-available/${SERVICE_NAME}" <<EOF
# PawsLedger Nginx Configuration
# Local reverse proxy: cloudflared → Nginx (${NGINX_PORT}) → Gunicorn (${APP_PORT})

upstream pawsledger_backend {
    server 127.0.0.1:${APP_PORT};
}

server {
    listen 127.0.0.1:${NGINX_PORT};
    server_name ${DOMAIN};

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Max upload size
    client_max_body_size 10M;

    # Proxy all requests to Gunicorn
    location / {
        proxy_pass http://pawsledger_backend;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;

        # WebSocket support (required for NiceGUI)
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
        proxy_set_header X-Forwarded-Proto https;
        proxy_read_timeout 86400;
        proxy_send_timeout 86400;
    }

    # Static files (served directly by Nginx)
    location /static/ {
        alias ${APP_DIR}/app/ui/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }
}
EOF

ln -sf "/etc/nginx/sites-available/${SERVICE_NAME}" "/etc/nginx/sites-enabled/${SERVICE_NAME}"
nginx -t
info "Nginx configured (listening on 127.0.0.1:${NGINX_PORT})."

# ─────────────────────────────────────────────────────────────
step "Step 10: Cloudflare Tunnel Service"
# ─────────────────────────────────────────────────────────────
echo ""
echo "─── Cloudflare Tunnel Setup ───"
echo ""
echo "To get your tunnel token:"
echo "  1. Go to Cloudflare Zero Trust → Networks → Tunnels"
echo "  2. Create a tunnel (or use existing) named 'pawsledger'"
echo "  3. Under Public Hostname, add:"
echo "     - Subdomain: (your subdomain, e.g. 'paws')"
echo "     - Domain: (your domain)"
echo "     - Service Type: HTTP"
echo "     - URL: localhost:${NGINX_PORT}"
echo "  4. Copy the tunnel token from the Install connector step"
echo ""
read -rp "Cloudflare Tunnel Token (paste here): " TUNNEL_TOKEN

if [[ -z "${TUNNEL_TOKEN}" ]]; then
    warn "No tunnel token provided. Skipping tunnel service setup."
    warn "You can set it up manually later with:"
    echo "  sudo cloudflared service install <YOUR_TOKEN>"
else
    # Install cloudflared as a system service with the token
    cloudflared service install "${TUNNEL_TOKEN}"
    info "Cloudflare Tunnel service installed and running."
fi

# ─────────────────────────────────────────────────────────────
step "Step 11: Start Services"
# ─────────────────────────────────────────────────────────────
systemctl restart "${SERVICE_NAME}"
systemctl restart nginx
info "Gunicorn and Nginx started."

# ─────────────────────────────────────────────────────────────
step "Step 12: Verify Deployment"
# ─────────────────────────────────────────────────────────────
sleep 3

echo ""
if systemctl is-active --quiet "${SERVICE_NAME}"; then
    info "✓ Gunicorn service is running."
else
    warn "✗ Gunicorn service may not be running."
    echo "  Check: sudo systemctl status ${SERVICE_NAME}"
fi

if systemctl is-active --quiet nginx; then
    info "✓ Nginx is running."
else
    warn "✗ Nginx may not be running."
    echo "  Check: sudo systemctl status nginx"
fi

if systemctl is-active --quiet cloudflared 2>/dev/null; then
    info "✓ Cloudflare Tunnel is running."
else
    warn "✗ Cloudflare Tunnel may not be running."
    echo "  Check: sudo systemctl status cloudflared"
fi

# ─── Summary ─────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
info "PawsLedger deployment complete!"
echo ""
echo "  Domain:         https://${DOMAIN}"
echo "  App directory:  ${APP_DIR}"
echo "  Data directory: ${DATA_DIR}"
echo "  Config file:    ${ENV_FILE}"
echo "  Logs:           /var/log/${SERVICE_NAME}/"
echo ""
echo "  ┌─────────────────────────────────────────────────────────┐"
echo "  │  Architecture:                                          │"
echo "  │                                                         │"
echo "  │  Client → Cloudflare (SSL) → cloudflared (tunnel)       │"
echo "  │              → Nginx (${NGINX_PORT}) → Gunicorn (${APP_PORT})          │"
echo "  │                  ↕ WebSocket    ↕ Uvicorn Workers        │"
echo "  │                                 NiceGUI + FastAPI        │"
echo "  │                                                         │"
echo "  │  Firewall: Only SSH open. No HTTP/HTTPS ports exposed.  │"
echo "  └─────────────────────────────────────────────────────────┘"
echo ""
echo "  Cloudflare Tunnel config (in dashboard):"
echo "    Public Hostname: ${DOMAIN}"
echo "    Service Type:    HTTP"
echo "    Service URL:     localhost:${NGINX_PORT}"
echo ""
echo "  Useful commands:"
echo "    sudo systemctl status ${SERVICE_NAME}    # App status"
echo "    sudo systemctl restart ${SERVICE_NAME}   # Restart app"
echo "    sudo systemctl status cloudflared        # Tunnel status"
echo "    sudo journalctl -u ${SERVICE_NAME} -f    # Live app logs"
echo "    sudo journalctl -u cloudflared -f        # Tunnel logs"
echo "    sudo tail -f /var/log/${SERVICE_NAME}/error.log"
echo "    sudo nginx -t && sudo systemctl restart nginx"
echo ""
echo "  Deploy updates:"
echo "    sudo su - ${APP_USER}"
echo "    cd ~/paws-ledger"
echo "    source .venv/bin/activate"
echo "    # pull/rsync new code, then:"
echo "    pip install -r requirements.txt"
echo "    exit"
echo "    sudo systemctl restart ${SERVICE_NAME}"
echo "═══════════════════════════════════════════════════════════════"
