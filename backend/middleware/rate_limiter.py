import time
import threading


rate_limit_store = {}
rate_limit_lock = threading.Lock()


def check_rate_limit(max_requests, window_seconds):
    from flask import request
    ip = request.remote_addr
    now = time.time()
    key = f"rl:{ip}"
    
    with rate_limit_lock:
        if key not in rate_limit_store:
            rate_limit_store[key] = []
        
        rate_limit_store[key] = [t for t in rate_limit_store[key] if now - t < window_seconds]
        
        if len(rate_limit_store[key]) >= max_requests:
            return False
        
        rate_limit_store[key].append(now)
        return True
