import hashlib
import os
import secrets
from typing import Optional, Set
from urllib.parse import urlparse
from fastapi import HTTPException, Request, Response, status

COOKIE_NAME = "kuku_session"

# Cookie security config: Secure in production/preview or when SECURE_COOKIES=true
IS_VERCEL = os.getenv("VERCEL") == "1" or bool(os.getenv("VERCEL_ENV"))
IS_PRODUCTION = (
    os.getenv("ENVIRONMENT", "development").lower() in ("production", "prod")
    or os.getenv("VERCEL_ENV") in ("production", "preview")
    or IS_VERCEL
)
SECURE_COOKIES = os.getenv("SECURE_COOKIES", "true" if IS_PRODUCTION else "false").lower() == "true"
ALLOW_VERCEL_PREVIEWS = os.getenv("ALLOW_VERCEL_PREVIEWS", "true").lower() == "true"

# Allowed origins for CSRF / origin validation on state-changing requests
DEFAULT_ALLOWED_ORIGINS = {
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
}


def _normalize_origin(url_or_host: str) -> str:
    """Ensure an origin host or URL has https:// prefix and no trailing slash."""
    clean = url_or_host.strip().rstrip("/")
    if not clean.startswith("http://") and not clean.startswith("https://"):
        return f"https://{clean}"
    return clean


def get_trusted_origins() -> Set[str]:
    """
    Construct exact trusted origins derived from:
    1. Default local development origins.
    2. Explicitly configured ALLOWED_ORIGINS or CORS_ORIGINS environment variables.
    3. Exact project deployment origins derived from trusted Vercel system environment variables:
       - VERCEL_URL (the URL of this specific deployment)
       - VERCEL_PROJECT_PRODUCTION_URL (the canonical production domain)
       - VERCEL_BRANCH_URL (the branch alias deployment URL)
    Wildcards like *.vercel.app are intentionally omitted to prevent cross-origin abuse
    from untrusted third-party deployments on Vercel.
    """
    trusted = set(DEFAULT_ALLOWED_ORIGINS)

    # Configured custom origins
    for env_var in ("ALLOWED_ORIGINS", "CORS_ORIGINS"):
        val = os.getenv(env_var, "")
        for orig in val.split(","):
            if orig.strip():
                trusted.add(_normalize_origin(orig))

    # Trusted Vercel deployment variables
    for v_var in ("VERCEL_URL", "VERCEL_PROJECT_PRODUCTION_URL", "VERCEL_BRANCH_URL"):
        host = os.getenv(v_var, "").strip()
        if host:
            trusted.add(_normalize_origin(host))

    return trusted


ALLOWED_ORIGINS: Set[str] = get_trusted_origins()


def generate_session_secret() -> str:
    """Generate a cryptographically secure 256-bit random session secret."""
    return secrets.token_urlsafe(32)


def hash_session_secret(secret: str) -> str:
    """Compute SHA-256 digest of the session secret for server-side persistence."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def validate_request_origin(request: Request) -> None:
    """
    Enforce origin validation on state-changing requests (POST, PUT, DELETE, PATCH).
    Protects against cross-origin request forgery.
    """
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        origin = request.headers.get("origin")
        referer = request.headers.get("referer")

        candidate_origin = None
        if origin:
            candidate_origin = origin.rstrip("/")
        elif referer:
            parsed = urlparse(referer)
            if parsed.scheme and parsed.netloc:
                candidate_origin = f"{parsed.scheme}://{parsed.netloc}"

        if candidate_origin:
            # 1. Exact match with current request origin (same-origin requests)
            request_origin = f"{request.url.scheme}://{request.url.netloc}".rstrip("/")
            if candidate_origin == request_origin:
                return

            # 2. Exact match against trusted origins (local dev, exact Vercel project domains, configured domains)
            trusted = get_trusted_origins()
            if candidate_origin in trusted:
                return

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cross-origin request rejected: origin '{candidate_origin}' not allowed.",
            )


def get_or_create_session_hash(request: Request, response: Response) -> str:
    """
    FastAPI dependency that extracts the session secret from HttpOnly cookie,
    hashes it for server-side lookup, or issues a new cryptographically random secret.
    Enforces Secure cookies on HTTPS connections (including Vercel previews) and production.
    """
    secret = request.cookies.get(COOKIE_NAME)
    is_secure = (
        SECURE_COOKIES
        or (request.url.scheme == "https")
        or (request.headers.get("x-forwarded-proto") == "https")
    )

    if not secret or len(secret) < 16:
        secret = generate_session_secret()
        response.set_cookie(
            key=COOKIE_NAME,
            value=secret,
            httponly=True,
            samesite="lax",
            secure=is_secure,
            path="/",
            max_age=60 * 60 * 24 * 30,  # 30 days
        )

    return hash_session_secret(secret)
