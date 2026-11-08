from fastapi import APIRouter, HTTPException, status
from app.schemas.promo import PromoAnalysisRequest, PromoAnalysisResponse
from app.services.ai.base import (
    AIModelNotFoundError,
    AIMissingCredentialsError,
    AIProviderError,
    AIQuotaExceededError,
    AIRefusalError,
    AITimeoutError,
)
from app.services.ai.orchestrator import analyze_episode_for_promos

router = APIRouter()

MAX_EVENTS_LIMIT = 500  # Guardrail against abusive payloads


@router.post("/promos/analyze", response_model=PromoAnalysisResponse)
def analyze_promo_candidates(request: PromoAnalysisRequest) -> PromoAnalysisResponse:
    """Analyze a single validated episode for continuous promo candidates.

    Submits the screenplay to Gemini, validates timeline boundaries, and computes
    editorial rankings without requiring database persistence.
    """
    episode = request.episode

    if not episode.events:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The supplied episode contains no timed events for promo analysis.",
        )

    if len(episode.events) > MAX_EVENTS_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Episode contains {len(episode.events)} events, exceeding the maximum allowed limit ({MAX_EVENTS_LIMIT}).",
        )

    try:
        response = analyze_episode_for_promos(
            episode=episode,
            max_candidates=request.max_candidates,
            model_override=request.model_override,
        )
        return response

    except AIMissingCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Gemini API key is not configured: {exc}",
        )
    except AIQuotaExceededError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Gemini API rate limit or quota exceeded: {exc}",
        )
    except AIModelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requested AI model not found: {exc}",
        )
    except AITimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"AI request timed out: {exc}",
        )
    except AIRefusalError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"AI model refused request: {exc}",
        )
    except AIProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI provider generation error: {exc}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during promo candidate analysis: {exc}",
        )

