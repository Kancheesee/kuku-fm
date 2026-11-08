import json
import os
import re
import time
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from pydantic import BaseModel

from app.schemas.promo import (
    BatchedAssessmentPayload,
    CandidateAssessmentItem,
    RawCandidateProposal,
)
from app.services.ai.base import (
    AIModelNotFoundError,
    AIMissingCredentialsError,
    AIProvider,
    AIProviderError,
    AIQuotaExceededError,
    AIRefusalError,
    AITimeoutError,
    AssessmentResult,
    GenerationResult,
)
from app.services.ai.prompts import ASSESSMENT_PROMPT_VERSION, PROMPT_VERSION

# Ensure local .env is loaded
load_dotenv(".env")

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
MAX_RETRIES = 1
REQUEST_TIMEOUT_SECONDS = 25


class PromoGenerationPayload(BaseModel):
    candidates: List[RawCandidateProposal]


def clean_json_text(text: str) -> str:
    """Strip markdown code fence blocks if returned by model."""
    cleaned = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if match:
        return match.group(1).strip()
    return cleaned


class GeminiProvider(AIProvider):
    """Gemini AI Provider using the official Google GenAI SDK (google-genai)."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.default_model = model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
        self._client = None

    def _get_client(self):
        if not self.api_key:
            raise AIMissingCredentialsError(
                "GEMINI_API_KEY is not configured in the environment or .env file."
            )
        if self._client is None:
            try:
                from google import genai
                from google.genai import types

                # Bound SDK-level timeout and restrict internal retries to 1 attempt
                # so our application loop deterministically controls backoff and total duration.
                http_opts = types.HttpOptions(
                    timeout=REQUEST_TIMEOUT_SECONDS * 1000,
                    retry_options=types.HttpRetryOptions(attempts=1),
                )
                self._client = genai.Client(api_key=self.api_key, http_options=http_opts)
            except Exception as e:
                raise AIProviderError(f"Failed to initialize Google GenAI client: {e}")
        return self._client

    def generate_candidates(
        self,
        system_prompt: str,
        user_prompt: str,
        model_override: Optional[str] = None,
    ) -> GenerationResult:
        client = self._get_client()
        target_model = model_override or self.default_model

        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=PromoGenerationPayload,
            temperature=0.2,
            max_output_tokens=4096,
        )

        attempts = 0
        last_error = None
        start_time = time.time()

        while attempts <= MAX_RETRIES:
            attempts += 1
            try:
                response = client.models.generate_content(
                    model=target_model,
                    contents=user_prompt,
                    config=config,
                )
                latency_ms = int((time.time() - start_time) * 1000)

                token_usage: Dict[str, Any] = {}
                usage_meta = getattr(response, "usage_metadata", None)
                if usage_meta:
                    token_usage = {
                        "prompt_tokens": getattr(usage_meta, "prompt_token_count", None),
                        "candidates_tokens": getattr(usage_meta, "candidates_token_count", None),
                        "total_tokens": getattr(usage_meta, "total_token_count", None),
                    }

                raw_text = response.text or ""
                cleaned = clean_json_text(raw_text)

                if not cleaned:
                    candidates = getattr(response, "candidates", [])
                    if candidates:
                        finish_reason = getattr(candidates[0], "finish_reason", None)
                        if finish_reason and finish_reason != "STOP":
                            raise AIRefusalError(f"Model generation stopped with finish reason: {finish_reason}")
                    raise AIProviderError("Model returned an empty response.")

                try:
                    data = json.loads(cleaned)
                    parsed_payload = PromoGenerationPayload.model_validate(data)
                    return GenerationResult(
                        raw_response_text=raw_text,
                        parsed_candidates=parsed_payload.candidates,
                        model_identifier=target_model,
                        prompt_version=PROMPT_VERSION,
                        token_usage=token_usage,
                        latency_ms=latency_ms,
                    )
                except Exception as parse_err:
                    try:
                        raw_list = json.loads(cleaned)
                        if isinstance(raw_list, list):
                            items = [RawCandidateProposal.model_validate(x) for x in raw_list]
                            return GenerationResult(
                                raw_response_text=raw_text,
                                parsed_candidates=items,
                                model_identifier=target_model,
                                prompt_version=PROMPT_VERSION,
                                token_usage=token_usage,
                                latency_ms=latency_ms,
                            )
                    except Exception:
                        pass
                    raise AIProviderError(f"Malformed JSON returned by model: {parse_err}")

            except Exception as e:
                err_str = str(e)
                status_code = getattr(e, "code", None)
                if not status_code and "404" in err_str:
                    status_code = 404
                elif not status_code and "429" in err_str:
                    status_code = 429
                elif not status_code and "503" in err_str:
                    status_code = 503

                if status_code == 404 or "NOT_FOUND" in err_str:
                    raise AIModelNotFoundError(
                        f"Model '{target_model}' was not found or is unavailable to this API key."
                    )
                elif status_code == 429 or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                    if attempts <= MAX_RETRIES:
                        time.sleep(1.5 * attempts)
                        continue
                    raise AIQuotaExceededError(
                        f"Gemini API rate limit or quota exceeded for model '{target_model}'. Error: {e}"
                    )
                elif status_code in (500, 503, 504) or "overloaded" in err_str.lower():
                    if attempts <= MAX_RETRIES:
                        time.sleep(2.0 * attempts)
                        continue
                    raise AIProviderError(f"Gemini service temporarily unavailable: {e}")
                elif "deadline" in err_str.lower() or "timeout" in err_str.lower():
                    raise AITimeoutError(f"Gemini request timed out: {e}")
                elif isinstance(e, (AIProviderError, AIRefusalError)):
                    raise
                else:
                    last_error = e

        raise AIProviderError(f"Generation failed after {attempts} attempts: {last_error}")

    def assess_candidates(
        self,
        system_prompt: str,
        user_prompt: str,
        model_override: Optional[str] = None,
    ) -> AssessmentResult:
        client = self._get_client()
        target_model = model_override or self.default_model

        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=BatchedAssessmentPayload,
            temperature=0.1,
            max_output_tokens=4096,
        )

        attempts = 0
        last_error = None
        start_time = time.time()

        while attempts <= MAX_RETRIES:
            attempts += 1
            try:
                response = client.models.generate_content(
                    model=target_model,
                    contents=user_prompt,
                    config=config,
                )
                latency_ms = int((time.time() - start_time) * 1000)

                token_usage: Dict[str, Any] = {}
                usage_meta = getattr(response, "usage_metadata", None)
                if usage_meta:
                    token_usage = {
                        "prompt_tokens": getattr(usage_meta, "prompt_token_count", None),
                        "candidates_tokens": getattr(usage_meta, "candidates_token_count", None),
                        "total_tokens": getattr(usage_meta, "total_token_count", None),
                    }

                raw_text = response.text or ""
                cleaned = clean_json_text(raw_text)

                if not cleaned:
                    raise AIProviderError("Model returned an empty assessment response.")

                try:
                    data = json.loads(cleaned)
                    parsed_payload = BatchedAssessmentPayload.model_validate(data)
                    return AssessmentResult(
                        raw_response_text=raw_text,
                        assessments=parsed_payload.assessments,
                        model_identifier=target_model,
                        prompt_version=ASSESSMENT_PROMPT_VERSION,
                        token_usage=token_usage,
                        latency_ms=latency_ms,
                    )
                except Exception as parse_err:
                    try:
                        raw_list = json.loads(cleaned)
                        if isinstance(raw_list, list):
                            items = [CandidateAssessmentItem.model_validate(x) for x in raw_list]
                            return AssessmentResult(
                                raw_response_text=raw_text,
                                assessments=items,
                                model_identifier=target_model,
                                prompt_version=ASSESSMENT_PROMPT_VERSION,
                                token_usage=token_usage,
                                latency_ms=latency_ms,
                            )
                    except Exception:
                        pass
                    raise AIProviderError(f"Malformed assessment JSON returned by model: {parse_err}")

            except Exception as e:
                err_str = str(e)
                status_code = getattr(e, "code", None)
                if not status_code and "404" in err_str:
                    status_code = 404
                elif not status_code and "429" in err_str:
                    status_code = 429
                elif not status_code and "503" in err_str:
                    status_code = 503

                if status_code == 404 or "NOT_FOUND" in err_str:
                    raise AIModelNotFoundError(f"Model '{target_model}' not found.")
                elif status_code == 429 or "RESOURCE_EXHAUSTED" in err_str:
                    if attempts <= MAX_RETRIES:
                        time.sleep(1.5 * attempts)
                        continue
                    raise AIQuotaExceededError(f"Rate limit exceeded during assessment: {e}")
                elif status_code in (500, 503, 504):
                    if attempts <= MAX_RETRIES:
                        time.sleep(2.0 * attempts)
                        continue
                    raise AIProviderError(f"Gemini service unavailable during assessment: {e}")
                elif isinstance(e, (AIProviderError, AIRefusalError)):
                    raise
                else:
                    last_error = e

        raise AIProviderError(f"Assessment failed after {attempts} attempts: {last_error}")
