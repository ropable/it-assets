# Gunicorn configuration settings.

bind = ":8080"
workers = 4
max_requests = 2048  # Max no of requests a worker will process before restarting
max_requests_jitter = 256  # Max jitter added to the max_requests setting
preload_app = True
keepalive = 5  # Max seconds to wait for requests on a Keep-Alive connection
timeout = 60  # Worker timeout
graceful_timeout = 30  # Graceful shutdown timeout
# Disable access logging.
accesslog = None
control_socket = "/tmp/gunicorn.ctl"
