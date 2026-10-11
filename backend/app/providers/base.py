from typing import Callable, Protocol
from ..models import GenerationRequest, ImageResult


class ProviderError(Exception):
    """Only user-safe messages belong in these exceptions."""


class SubmissionUncertain(ProviderError):
    pass


class TextProvider(Protocol):
    async def complete_json(self, system: str, content: str, schema: dict) -> dict: ...


class ImageProvider(Protocol):
    supports_edit: bool
    async def generate(self, request: GenerationRequest, on_submitted: Callable[[str], None] | None = None) -> ImageResult: ...
