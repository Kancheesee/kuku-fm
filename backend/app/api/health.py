from fastapi import APIRouter
from app.db.session import check_db_connection
from app.schemas.models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Basic health check reporting service status and whether database is connected."""
    db_connected = check_db_connection()
    return HealthResponse(
        status="ok",
        version="0.1.0",
        database_connected=db_connected,
    )

