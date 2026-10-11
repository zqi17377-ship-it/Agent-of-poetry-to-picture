import base64
import json
import mimetypes
from .base import ProviderError
from .http_utils import client_context, post_json, decode_image, verify_image
from ..models import GenerationRequest, ImageResult


class GeminiProvider:
    supports_edit = True

    def __init__(self, key: str, text_model="gemini-2.5-flash", image_model="gemini-nano-banana-2.1", client=None):
        self.key, self.text_model, self.image_model, self.client = key, text_model, image_model, client
        self.last_usage = None

    async def _generate(self, model: str, body: dict):
        if not self.key:
            raise ProviderError("请先在 .env 中配置 GEMINI_API_KEY，或切换到免费 FLUX 演示。")
        if not model or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._" for c in model):
            raise ProviderError("模型名称格式不正确。")
        async with client_context(self.client) as client:
            return await post_json(client, f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", body, {"x-goog-api-key": self.key})

    async def complete_json(self, system, content, schema):
        result = await self._generate(self.text_model, {"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": [{"text": content}]}], "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": schema}})
        self.last_usage = result.get("usageMetadata")
        try:
            parts = result["candidates"][0]["content"]["parts"]
            return json.loads("".join(part.get("text", "") for part in parts if not part.get("thought")))
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ProviderError("文学模型没有返回有效的结构化理解。") from error

    async def generate(self, request: GenerationRequest, on_submitted=None) -> ImageResult:
        parts = [{"text": request.prompt}]
        if request.reference_path:
            parts.append({"inlineData": {"mimeType": mimetypes.guess_type(request.reference_path.name)[0] or "image/png", "data": base64.b64encode(request.reference_path.read_bytes()).decode()}})
        result = await self._generate(self.image_model, {"contents": [{"role": "user", "parts": parts}], "generationConfig": {"responseModalities": ["TEXT", "IMAGE"], "imageConfig": {"aspectRatio": request.aspect_ratio}}})
        for candidate in result.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                inline = part.get("inlineData")
                if inline and inline.get("mimeType", "").startswith("image/"):
                    data = decode_image(inline.get("data", ""))
                    return ImageResult(data, verify_image(data), self.image_model, result.get("responseId"), result.get("usageMetadata"))
        raise ProviderError("模型没有返回图片，可能是不支持图像输出或内容被拒绝。")
