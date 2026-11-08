from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from app.schemas.promo import CandidateAssessmentItem, RawCandidateProposal


class GenerationResult(BaseModel):
    raw_response_text: str
    parsed_candidates: List[RawCandidateProposal]
    model_identifier: str
    prompt_version: str
    token_usage: Dict[str, Any]
    latency_ms: int
    error: Optional[str] = None


class AssessmentResult(BaseModel):
    raw_response_text: str
    assessments: List[CandidateAssessmentItem]
    model_identifier: str
    prompt_version: str
    token_usage: Dict[str, Any]
    latency_ms: int
    error: Optional[str] = None


class AIProviderError(Exception):
    """Base exception for AI provider operations."""
    pass


class AIMissingCredentialsError(AIProviderError):
    """API key or required credentials are missing."""
    pass


class AIQuotaExceededError(AIProviderError):
    """API rate limit or quota exceeded."""

    def __init__(self, message: str, partial_result: Optional[Any] = None):
        super().__init__(message)
        self.partial_result = partial_result


class AIModelNotFoundError(AIProviderError):
    """Specified model is unavailable or not found."""
    pass


class AITimeoutError(AIProviderError):
    """Model request timed out."""
    pass


class AIRefusalError(AIProviderError):
    """Model refused the request due to safety or policy."""
    pass


class AIProvider(ABC):
    """Replaceable provider abstraction for promo candidate generation and assessment."""

    @abstractmethod
    def generate_candidates(
        self,
        system_prompt: str,
        user_prompt: str,
        model_override: Optional[str] = None,
    ) -> GenerationResult:
        """Submit generation prompt to model and return structured proposals."""
        pass

    @abstractmethod
    def assess_candidates(
        self,
        system_prompt: str,
        user_prompt: str,
        model_override: Optional[str] = None,
    ) -> AssessmentResult:
        """Submit batched assessment prompt to model and return structured rubric scores."""
        pass
