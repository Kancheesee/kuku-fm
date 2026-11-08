from enum import Enum
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class EventCategory(str, Enum):
    CAMERA = "camera"
    ACTION = "action"
    DIALOGUE = "dialogue"
    SOUND_EFFECT = "sound_effect"
    UNKNOWN = "unknown"


class IssueSeverity(str, Enum):
    WARNING = "warning"
    ERROR = "error"


class ParsingIssue(BaseModel):
    severity: IssueSeverity
    code: str
    message: str
    line: Optional[int] = None
    line_end: Optional[int] = None


class Event(BaseModel):
    id: str
    scene_id: str
    category: EventCategory
    original_label: str
    speaker: Optional[str] = None
    delivery_notes: Optional[str] = None
    start_ms: int
    end_ms: int
    text: str
    line_start: int
    line_end: int


class Scene(BaseModel):
    id: str
    scene_label: str
    heading: str
    start_ms: int
    end_ms: int
    line_start: int
    line_end: int


class Episode(BaseModel):
    id: str
    episode_number: Optional[int] = None
    filename: str
    logline: Optional[str] = None
    continuity_notes: Optional[str] = None
    duration_ms: int
    scenes: List[Scene] = Field(default_factory=list)
    events: List[Event] = Field(default_factory=list)
    warnings: List[ParsingIssue] = Field(default_factory=list)
    content_hash: str
    parser_version: str


class IngestFileResult(BaseModel):
    filename: str
    success: bool
    episode: Optional[Episode] = None
    issues: List[ParsingIssue] = Field(default_factory=list)


class IngestPreviewResponse(BaseModel):
    episodes: List[Episode] = Field(default_factory=list)
    total_episodes: int = 0
    total_runtime_ms: int = 0
    total_events: int = 0
    total_issues: int = 0
    ignored_files_count: int = 0
    file_results: List[IngestFileResult] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str = "0.1.0"
    database_connected: bool = False
