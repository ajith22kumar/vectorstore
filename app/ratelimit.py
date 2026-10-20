import time
from collections import defaultdict, deque
from fastapi import HTTPException, Request
from .config import settings
requests_by_ip = defaultdict(deque)
def rate_limit(request: Request):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    window = requests_by_ip[ip]
    while window and window[0] < now - 60:
        window.popleft()
    if len(window) >= settings.rate_limit_per_minute:
        raise HTTPException(status_code=429, detail="Too many requests, try again in a minute")
    window.append(now)