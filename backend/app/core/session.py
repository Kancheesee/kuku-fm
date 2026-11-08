import hashlib
import os
import secrets
from typing import Optional, Set
from urllib.parse import urlparse
from fastapi import HTTPException, Request, Response, status

COOKIE_NAME = "kuku_session"

# Cookie security config: Secure in production or when SECURE_COOKIES=true
IS_PRODUCTION = os.getenv("ENVIRONMENT", "development").lower() in ("production", "prod")
SECURE_COOKIES = os.getenv("SECURE_COOKIES", "true" if IS_PRODUCTION else "false").lower() == "true"

# Allowed origins for CSRF / origin validation on state-changing requests
DEFAULT_ALLOWED_ORIGINS = {
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
}
CUSTOM_ALLOWED_ORIGINS = {
    orig.strip()
    for orig in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if orig.strip()
}
ALLOWED_ORIGINS: Set[str] = DEFAULT_ALLOWED_ORIGINS | CUSTOM_ALLOWED_ORIGINS


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
            # Check against allowed list or matching base URL hostname/netloc
            request_origin = f"{request.url.scheme}://{request.url.netloc}".rstrip("/")
            if (
                candidate_origin not in ALLOWED_ORIGINS
                and candidate_origin != request_origin
                and not any(candidate_origin.endswith(allowed.replace("https://", ".").replace("http://", ".")) for allowed in CUSTOM_ALLOWED_ORIGINS)
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Cross-origin request rejected: origin '{candidate_origin}' not allowed.",
                )


def get_or_create_session_hash(request: Request, response: Response) -> str:
    """
    FastAPI dependency that extracts the session secret from HttpOnly cookie,
    hashes it for server-side lookup, or issues a new cryptographically random secret.
    """
    secret = request.cookies.get(COOKIE_NAME)
    if not secret or len(secret) < 16:
        secret = generate_session_secret()
        response.set_cookie(
            key=COOKIE_NAME,
            value=secret,
            httponly=True,
            samesite="lax",
            secure=SECURE_COOKIES,
            path="/",
            max_age=60 * 60 * 24 * 30,  # 30 days
        )

    return hash_session_secret(secret)
