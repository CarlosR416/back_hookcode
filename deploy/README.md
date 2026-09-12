# Production Architecture & Deployment Guide: back hookcode API

This document describes the end-to-end production architecture and deployment guidelines for the **back hookcode API**.

---

## 🏛️ End-to-End System Architecture

The overall platform is divided into decoupled infrastructure tiers across separate machines:

```
[Client / Browser]
       │ (HTTPS)
       ▼
[Cloudflare Edge CDN]
  ├── SSL/TLS Mode: "Full"
  ├── Proxied (Orange Cloud) for your API domain
  └── Forwards: Host, X-Forwarded-Proto, CF-Connecting-IP
       │ (HTTPS - Port 443 with self-signed certificate on proxy IP)
       ▼
[Machine 1: Proxy Gateway (Nginx)]
  ├── SSL Termination: Self-signed certificate matching server IP
  ├── Static Files Disk Cache: /static/ cached on disk (7 days)
  ├── NAT & Port Forwarding: Persistent SSH and HTTP routing
  └── Upstream: proxy_pass http://<backend_private_ip>:8000
       │ (Unencrypted HTTP over trusted internal private network)
       ▼
[Machine 2: Application Backend (Debian Server)]
  ├── Service Manager: Systemd / Supervisor (optional)
  ├── Entrypoint Script: deploy/start_api.sh (auto-venv & dependency sync)
  ├── WSGI Server: Gunicorn (multi-worker with gthread)
  ├── Runtime: Python 3.13 Virtual Environment
  ├── Application: Django REST Framework
  └── External Configuration: Loaded from ../.env
       │ (TCP / SSL with connection keepalive pool)
       ▼
[Database Tier: Managed PostgreSQL]
  ├── Persistent Connections (CONN_MAX_AGE = 60s)
  └── Isolated schema & credentials
```

### Architectural Principles

1. **Two-Server Separation & Trusted Network Model:**
   - **Machine 1 (Proxy Gateway):** Dedicated machine that faces the public internet, terminates incoming TLS from Cloudflare, and caches static assets.
   - **Machine 2 (Application Backend):** Dedicated machine isolated within a private network. It accepts traffic only from the Proxy Gateway.
   - **Unencrypted Internal Hop:** Because communication between Machine 1 and Machine 2 occurs over a secure, trusted private network, traffic travels via plain HTTP (`http://<backend_private_ip>:8000`). This avoids double-encryption CPU overhead while keeping external traffic fully encrypted.
   - Django uses `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` and `USE_X_FORWARDED_HOST = True` to reconstruct incoming HTTPS contexts transparently.

2. **Edge Static Caching (7 Days Retention):**
   - The Proxy Gateway inspects `/static/` requests and serves them directly from a local disk cache with a 7-day retention period (`Cache-Control: public, max-age=604800, immutable`).
   - Static asset requests are absorbed by the proxy without reaching application workers or database connections.

3. **Persistent Firewall & VPN Isolation:**
   - The Proxy Gateway utilizes persistent NAT rules to forward administrative SSH traffic and public HTTP traffic to backend targets.
   - **VPN Internet Isolation:** Routers connecting to management VPN tunnels are strictly prevented from using the infrastructure as an open gateway to the internet. Traffic from VPN subnets is dropped on the forwarding chain.

4. **Resource Management & Keepalive:**
   - Gunicorn workers proactively recycle after processing requests (`max_requests`) to prevent memory degradation.
   - Database connections utilize persistent keepalive (`DB_CONN_MAX_AGE=60`) to reuse open sockets across requests, eliminating repeated TLS and TCP connection overhead.

---

## 📁 Repository Components

The following deployment components are maintained within this repository for the application backend service:

| File | Role |
| :--- | :--- |
| [`start_api.sh`](./start_api.sh) | Application entrypoint script. Resolves and links `.env`, auto-creates the Python virtual environment (`venv/`), installs production dependencies, applies migrations, collects static assets, and boots Gunicorn. |
| [`gunicorn.conf.py`](./gunicorn.conf.py) | Application server configuration. Defines concurrency workers, thread models, proactive request recycling limits, and structured logging. |
| [`.env.production.example`](./.env.production.example) | Production environment variable configuration template with security hardening defaults. |
| [`back.hookcode.service.example`](./back.hookcode.service.example) | Reference Systemd unit template for process supervision and sandboxing. Provided as an example; customize placeholders before use. |

---

## ⚙️ Backend Configuration Schema (`../.env`)

Environment variables are stored outside the project directory (e.g. `../.env`). Below is the generic configuration schema:

```ini
# ── Application Runtime ─────────────────────────────────────────────────────────
DEBUG=False
SECRET_KEY=<SECRET_KEY_MIN_50_CHARACTERS>

# Comma-separated list of allowed host headers (domain and backend private IP)
ALLOWED_HOSTS=<API_DOMAIN>,127.0.0.1,localhost,<BACKEND_INTERNAL_IP>

# Frontend domains allowed for Cross-Origin requests
CORS_ALLOWED_ORIGINS=https://<FRONTEND_APP_DOMAIN>

# Origins permitted to perform state-changing HTTPS requests
CSRF_TRUSTED_ORIGINS=https://<API_DOMAIN>,https://<FRONTEND_APP_DOMAIN>

# ── Database Layer (PostgreSQL) ────────────────────────────────────────────────
DB_ENGINE=django.db.backends.postgresql
DB_NAME=<DB_NAME>
DB_USER=<DB_USER>
DB_PASSWORD=<DB_PASSWORD>
DB_HOST=<DB_HOST>
DB_PORT=5432

# Connection persistence in seconds (reduces connection churn)
DB_CONN_MAX_AGE=60

# ── Security & Reverse Proxy ───────────────────────────────────────────────────
# Enforce HTTPS redirect (handled via X-Forwarded-Proto from external proxy)
SECURE_SSL_REDIRECT=True
```

---

## 🚀 Backend Deployment Instructions (Machine 2)

### 1. Prerequisites on Backend Server
Ensure system build tools and Python 3.13 are installed:
```bash
sudo apt-get update && sudo apt-get install -y \
    python3.13 python3.13-venv python3.13-dev \
    libpq-dev gcc curl git
```

### 2. Application Setup
1. Clone the repository to the deployment directory (e.g. `/var/www/back_hookcode`).
2. Place the environment configuration file at `../.env` relative to the repository root.
3. Make the startup script executable:
   ```bash
   chmod +x deploy/start_api.sh
   ```

### 3. Process Supervision (Optional Systemd Example)
If you wish to manage the process lifecycle via Systemd, an illustrative template is provided in [`deploy/back.hookcode.service.example`](./back.hookcode.service.example). **Do not use this file directly without adapting its configuration:**

1. Copy the example template to `/etc/systemd/system/` using your preferred service name:
   ```bash
   sudo cp deploy/back.hookcode.service.example /etc/systemd/system/<your-service-name>.service
   ```
2. Edit the service unit and adapt placeholders (`User`, `Group`, `WorkingDirectory`, and `ExecStart`):
   ```bash
   sudo nano /etc/systemd/system/<your-service-name>.service
   ```
3. Enable and start your service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable <your-service-name>
   sudo systemctl start <your-service-name>
   ```
4. Verify status and logs:
   ```bash
   sudo systemctl status <your-service-name>
   sudo journalctl -u <your-service-name> -f
   ```

*Note: On first execution, `start_api.sh` automatically creates the Python 3.13 virtual environment (`venv/`), installs all requirements from `requirements/production.txt`, applies database migrations, and prepares static files.*

---

## 🌐 External Infrastructure Requirements (Reference)

For reference, the external infrastructure components should be configured according to the following architectural standards:

### Proxy Gateway Requirements (Machine 1)
- **TLS Termination:** Configured with a self-signed certificate on the proxy host's public IP, enabling Cloudflare SSL in **Full** encryption mode.
- **Static Caching:** Caches `/static/` assets on local disk with a 7-day TTL (`proxy_cache_valid 200 7d`), serving static requests without hitting the backend.
- **Header Forwarding:** Must forward incoming client context to the private backend:
  - `Host: $host`
  - `X-Real-IP: $remote_addr`
  - `X-Forwarded-For: $proxy_add_x_forwarded_for`
  - `X-Forwarded-Proto: https`
  - `X-Forwarded-Host: $host`
  - `CF-Connecting-IP: $http_cf_connecting_ip`
- **Upstream Forwarding:** Forwards dynamic requests over the private network to `http://<backend_private_ip>:8000`.

### Firewall & Routing Requirements
- **Persistent NAT:** Port forwarding for SSH and HTTP must be persisted across reboots via `iptables-persistent` / `netfilter-persistent` with `net.ipv4.ip_forward = 1`.
- **VPN Transit Drop:** The forwarding chain must explicitly drop transit traffic originating from VPN client subnets to prevent open internet routing through the platform:
  ```bash
  iptables -A FORWARD -s <vpn_subnet> ! -d <vpn_subnet> -j DROP
  ```
