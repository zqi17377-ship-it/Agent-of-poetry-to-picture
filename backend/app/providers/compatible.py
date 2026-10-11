import json
from urllib.parse import urlparse
from .base import ProviderError
from .http_utils import client_context, post_json, decode_image, download_image, verify_image
from ..models import GenerationRequest, ImageResult


class CompatibleProvider:
    """Configurable chat/completions and images/generations protocol adapter."""
    supports_edit = False

    def __init__(self, base_url: str, key: str, model: str, allowed_hosts: str = "", client=None):
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("请配置正确的模型服务地址。")
        if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("远程模型接口必须使用 HTTPS。")
        self.base_url, self.key, self.model, self.client = base_url.rstrip("/"), key, model, client
        self.allowed_hosts = {parsed.hostname, *[host.strip() for host in allowed_hosts.split(",") if host.strip()]}
        self.last_usage = None

    def headers(self):
        return {"Authorization": "Bearer " + self.key} if self.key else {}

    async def complete_json(self, system, content, schema):
        async with client_context(self.client) as client:
            result = await post_json(client, self.base_url + "/chat/completions", {"model": self.model, "messages": [{"role": "system", "content": system + "\nRequired JSON schema: " + json.dumps(schema)}, {"role": "user", "content": content}], "response_format": {"type": "json_object"}}, self.headers())
        self.last_usage = result.get("usage")
        try:
            return json.loads(result["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ProviderError("文学模型没有返回有效的 JSON，请检查模型及结构化输出能力。") from error

    async def generate(self, request: GenerationRequest, on_submitted=None) -> ImageResult:
        if request.reference_path:
            raise ProviderError("当前兼容接口只启用了文字出图，请选择按描述重新生成。")
        size = {"3:2": "1536x1024", "1:1": "1024x1024", "2:3": "1024x1536"}[request.aspect_ratio]
        async with client_context(self.client) as client:
            result = await post_json(client, self.base_url + "/images/generations", {"model": self.model, "prompt": request.prompt, "n": 1, "size": size, "response_format": "b64_json"}, self.headers())
            try:
                item = result["data"][0]
            except (KeyError, IndexError, TypeError) as error:
                raise ProviderError("图像接口未返回有效图片。") from error
            if item.get("b64_json"):
                data = decode_image(item["b64_json"])
            elif item.get("url"):
                data = await download_image(client, item["url"], self.allowed_hosts)
            else:
                raise ProviderError("图像接口未返回图片数据或下载地址。")
            return ImageResult(data, verify_image(data), self.model, usage=result.get("usage"))
