"""gunicorn settings (docs/DEPLOYMENT.md section 2).

1 worker x 4 threads is deliberate: the LocMem cache and throttle counters are per process.
Adding workers silently splits both. Do not change without moving to a shared cache.
"""

import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = 1
threads = 4
worker_class = "gthread"
timeout = 60  # above the 25 s service deadline: a slow upstream yields a typed error, not a kill
graceful_timeout = 20
accesslog = None  # its default line logs the query string and client address
errorlog = "-"
