"""Health check endpoint."""

from fastapi import APIRouter

from app.schemas.document import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/api/v1/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Return the service health status. Useful for load balancers and monitoring.",
)
def get_health() -> HealthResponse:
    return HealthResponse(status="ok")
