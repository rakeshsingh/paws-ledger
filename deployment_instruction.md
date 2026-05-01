To deploy PawsLedger to an IONOS VPS with SSL enabled via Cloudflare Tunnel, follow these steps. This method is highly secure as it does not require opening any inbound ports on your VPS firewall.

## 1. Prepare Your VPS
First, SSH into your IONOS VPS as your primary user (e.g., `root` or `admin`).

### Install Docker
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt install -y docker-compose
```

### Create Dedicated Application User
```bash
# Create the user
sudo adduser --disabled-password --gecos "" pawsapp
sudo usermod -aG docker pawsapp
sudo mkdir -p /home/pawsapp/paws-ledger
sudo chown pawsapp:pawsapp /home/pawsapp/paws-ledger

# Switch to the new user
sudo su - pawsapp
```

## 2. Configure Cloudflare Tunnel (Zero Trust)
Before launching the app, you need to create a Tunnel in the Cloudflare Dashboard:

1.  Go to **Zero Trust** -> **Networks** -> **Tunnels**.
2.  Click **Create a Tunnel** and name it (e.g., `paws-ledger-vps`).
3.  Choose **Docker** as your environment.
4.  Copy the **Tunnel Token** provided in the command shown (it's the long string after `--token`).
5.  Go to the **Public Hostname** tab:
    *   **Public Hostname**: Your domain (e.g., `paws.yourdomain.com`).
    *   **Service Type**: `HTTP`
    *   **URL**: `app:8080` (This matches the service name in `docker-compose.yml`).

## 3. Upload Files & Configure Environment
Upload your project files to `/home/pawsapp/paws-ledger`.

As the `pawsapp` user, create your `.env` file:
```bash
cd ~/paws-ledger
cat <<EOF > .env
# Application Secrets
STORAGE_SECRET=$(openssl rand -hex 32)

# Google OAuth
GOOGLE_CLIENT_ID=your_google_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_secret_key
GOOGLE_CALLBACK_URL=https://your-domain.com/api/v1/auth/callback

# Cloudflare Tunnel
TUNNEL_TOKEN=your_copied_cloudflare_token_here
EOF
```

## 4. Launch the Application
```bash
docker-compose up --build -d
```

## 5. Security & Maintenance

*   **Firewall**: You can now go to your **IONOS Cloud Panel** and **remove/close all incoming Firewall rules** for port 80 and 8080. The application is only accessible through the secure Cloudflare Tunnel.
*   **SSL**: SSL is handled automatically by Cloudflare. Ensure your SSL/TLS settings in Cloudflare are set to **Full** or **Full (Strict)**.
*   **Logs**: To check if the tunnel is connected:
    ```bash
    docker-compose logs -f tunnel
    ```
