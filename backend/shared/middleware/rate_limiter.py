import time
from shared.models import db
from sqlalchemy import text


class RateLimit(db.Model):
    __tablename__ = 'rate_limit'
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False)
    window_start = db.Column(db.Integer, nullable=False)
    request_count = db.Column(db.Integer, default=0)

    __table_args__ = (
        db.Index('ix_rate_limit_ip_window', 'ip_address', 'window_start'),
    )


def check_rate_limit(max_requests, window_seconds):
    from flask import request
    ip = request.remote_addr
    now = time.time()
    window_start = int(now // window_seconds) * window_seconds

    try:
        with db.engine.begin() as conn:
            # Cleanup old entries (windows older than 2x the limit window)
            old_window = int((now - window_seconds * 2) // window_seconds) * window_seconds
            conn.execute(
                text("DELETE FROM rate_limit WHERE window_start < :old_window"),
                {"old_window": old_window}
            )

            result = conn.execute(
                text("SELECT request_count FROM rate_limit WHERE ip_address = :ip AND window_start = :window"),
                {"ip": ip, "window": window_start}
            )
            row = result.fetchone()

            if row:
                count = row[0] + 1
                conn.execute(
                    text("UPDATE rate_limit SET request_count = :count WHERE ip_address = :ip AND window_start = :window"),
                    {"count": count, "ip": ip, "window": window_start}
                )
            else:
                count = 1
                conn.execute(
                    text("INSERT INTO rate_limit (ip_address, window_start, request_count) VALUES (:ip, :window, 1)"),
                    {"ip": ip, "window": window_start}
                )

        return count <= max_requests
    except Exception:
        # Fail open: if rate limiter DB is unavailable, don't block requests
        return True
