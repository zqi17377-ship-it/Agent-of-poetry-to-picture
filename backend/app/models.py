from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class ArtworkInput(BaseModel):
    text: str
    title: str = Field(default="", max_length=200)
    author: str = Field(default="", max_length=200)
    aspect_ratio: Literal["3:2", "1:1", "2:3"] = "3:2"

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= 8000:
            raise ValueError("请输入 1–8000 字的诗文。")
        return value


class ImageryEvidence(BaseModel):
    image: str
    source_quote: str = Field(min_length=1)


class Interpretation(BaseModel):
    language: str
    emotions: list[str]
    imagery: list[ImageryEvidence]
    ambiguities: list[str]
    source_text: str = ""
    relations: list[str] = Field(default_factory=list, description="用中文描述原文意象之间的动作、方向、对立、时间或空间关系，避免只列出名词。")


class VisualAnchor(BaseModel):
    source_quote: str = Field(min_length=1)
    visual_element: str = Field(min_length=1, pattern="^[^㐀-鿿]*$", description="English only: a visible object and its physical arrangement in the same scene.")
    connection: str = Field(min_length=1)


class VisualBrief(BaseModel):
    subject: str = Field(max_length=200, pattern="^[^㐀-鿿]*$", description="English only; include the important visible objects.")
    setting: str = Field(max_length=220, pattern="^[^㐀-鿿]*$", description="English only; one coherent plausible location.")
    composition: str = Field(max_length=360, pattern="^[^㐀-鿿]*$", description="English only; position, scale, perspective and relationships of the objects.")
    lighting: str = Field(max_length=160, pattern="^[^㐀-鿿]*$", description="English only; natural light appropriate to the passage.")
    palette: str = Field(max_length=140, pattern="^[^㐀-鿿]*$", description="English only; restrained color, preserve warmth when present.")
    rendering: str = Field(max_length=160, pattern="^[^㐀-鿿]*$", description="English only; natural photographic material and texture.")
    additions: list[str]
    rationale: str
    anchors: list[VisualAnchor] = Field(default_factory=list)
    requested_adjustment: str = Field(default="", description="Only used by the legacy basic adapter to keep the user's untranslated revision; leave empty when designing with a language model.")


class RevisionInput(BaseModel):
    source_version_id: str
    instruction: str = Field(min_length=1, max_length=2000)
    mode: Literal["edit", "regenerate"] = "edit"

    @field_validator("instruction")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("请描述希望调整的画面。")
        return value.strip()


@dataclass
class GenerationRequest:
    prompt: str
    aspect_ratio: str = "3:2"
    reference_path: Path | None = None


@dataclass
class ImageResult:
    data: bytes
    mime_type: str
    model: str
    provider_request_id: str | None = None
    usage: dict | None = None


class QualityReport(BaseModel):
    flags: list[str] = Field(default_factory=list)
    rationale: str = "视觉评估未启用，请结合原文检查画面的自然程度。"


@dataclass
class JobRecord:
    id: str
    artwork_id: str
    status: str
    operation: str
    source_version_id: str | None = None
    instruction: str = ""
    stage: str = "queued"
    error: str | None = None
    provider_request_id: str | None = None
    call_count: int = 0
    elapsed_ms: int = 0
    usage: dict = field(default_factory=dict)
