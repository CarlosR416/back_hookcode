"""
Gunicorn configuration for back hookcode Debian production environment.

- Concurrency model: multi-worker with gthread worker class.
- max_requests and max_requests_jitter recycle workers periodically to eliminate memory leaks.
- Designed for stable and efficient production operation.
"""

import os

bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")
backlog = 512

# Concurrency tuning
workers = int(os.getenv("GUNICORN_WORKERS", "2"))
threads = int(os.getenv("GUNICORN_THREADS", "2"))
worker_class = "gthread"
worker_connections = 1000
timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))
keepalive = 5

# Memory management: recycle workers to prevent memory degradation
max_requests = 1000
max_requests_jitter = 100

# Process naming
proc_name = os.getenv("GUNICORN_PROC_NAME", "backend_api_service")

# Logging: output to stdout/stderr for systemd journald capture
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOGLEVEL", "info")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)sµs'
