import multiprocessing
import os

# Server socket
bind = "127.0.0.1:5050"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 300
keepalive = 2

# Restart workers after this many requests, with some jitter
max_requests = 1000
max_requests_jitter = 50

# Preload app for better memory usage
preload_app = True

# Logging
accesslog = "-"  # Log to stdout for systemd
errorlog = "-"   # Log to stderr for systemd
loglevel = "info"

# Process naming
proc_name = 'extraction-service'

# Server mechanics
daemon = False
pidfile = None
user = None
group = None
tmp_upload_dir = None

# SSL (if needed)
# keyfile = None
# certfile = None
