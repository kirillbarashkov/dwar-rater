import time
from shared.models import db
from sqlalchemy import text


class RateLimit(db.Model):
    __tablename__ = 'rate_limit'
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False)
    user_id = db.Column(db.Integer, nullable=True)
    window_start = db.Column(db.Integer, nullable=False)
    request_count = db.Column(db.Integer, default=0)

    __table_args__ = (
        db.Index('ix_rate_limit_ip_window', 'ip_address', 'window_start'),
        db.Index('ix_rate_limit_user_window', 'user_id', 'window_start'),
    )


def check_rate_limit(max_requests, window_seconds, user_id=None):
    """Sliding-window rate limit keyed per-user (authenticated) or per-IP.

    Authenticated requests count against a per-user bucket, anonymous ones
    against a per-IP bucket. Returns True if the request is allowed. Fails open
    if the DB is unavailable.
    """
    from flask import request
    ip = request.remote_addr or ''
    now = time.time()
    window_start = int(now // window_seconds) * window_seconds

    try:
        with db.engine.begin() as conn:
            # Prune stale windows regardless of key.
            old_window = int((now - window_seconds * 2) // window_seconds) * window_seconds
            conn.execute(
                text("DELETE FROM rate_limit WHERE window_start < :old_window"),
                {"old_window": old_window},
            )

            if user_id is not None:
                key_col, key = "user_id", user_id
            else:
                key_col, key = "ip_address", ip

            result = conn.execute(
                text(
                    "SELECT request_count FROM rate_limit "
                    f"WHERE {key_col} = :key AND window_start = :window"
                ),
                {"key": key, "window": window_start},
            )
            row = result.fetchone()

            if row:
                count = row[0] + 1
                conn.execute(
                    text(
                        "UPDATE rate_limit SET request_count = :count "
                        f"WHERE {key_col} = :key AND window_start = :window"
                    ),
                    {"count": count, "key": key, "window": window_start},
                )
            else:
                count = 1
                if user_id is not None:
                    conn.execute(
                        text(
                            "INSERT INTO rate_limit (ip_address, user_id, window_start, request_count) "
                            "VALUES (:ip, :key, :window, 1)"
                        ),
                        {"ip": ip, "key": key, "window": window_start},
                    )
                else:
                    conn.execute(
                        text(
                            "INSERT INTO rate_limit (ip_address, window_start, request_count) "
                            "VALUES (:key, :window, 1)"
                        ),
                        {"key": key, "window": window_start},
                    )

        return count <= max_requests
    except Exception:
        # Fail open: if rate limiter DB is unavailable, don't block requests
        return True