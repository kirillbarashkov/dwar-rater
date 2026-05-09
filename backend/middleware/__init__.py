# Re-export from shared.middleware for backward compatibility
from shared.middleware.auth import check_credentials, require_auth
from shared.middleware.rate_limiter import check_rate_limit
from shared.middleware.security import add_security_headers
