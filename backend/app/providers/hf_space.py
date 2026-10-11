import json
import secrets
from urllib.parse import urlparse
import httpx
from .base import ProviderError, SubmissionUncertain
from .http_utils import client_context, post_json, check_status, download_image, verify_image
from ..models import GenerationRequest, ImageResult


class HuggingFaceSpaceProvider:
    supports_edit = False

    def __init__(self, base_url: str, token: str = "", client=None):
        parsed = urlparse(base_url)
        if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".hf.space"):
            raise ValueError("免费演示地址必须是 HTTPS 的 Hugging Face Space。")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.client = client

    async def generate(self, request: GenerationRequest, on_submitted=None) -> ImageResult:
        if request.reference_path:
            raise ProviderError("免费 FLUX 演示不支持原图编辑，请选择按描述重新生成。")
        width, height = {"3:2": (768, 512), "1:1": (640, 640), "2:3": (512, 768)}[request.aspect_ratio]
        headers = {"Authorization": "Bearer " + self.token} if self.token else {}
        async with client_context(self.client) as client:
            result = await post_json(client, self.base_url + "/gradio_api/call/infer", {"data": [request.prompt, secrets.randbelow(2147483647), False, width, height, 4]}, headers)
            event_id = result.get("event_id")
            if not isinstance(event_id, str) or not event_id.isalnum():
                raise SubmissionUncertain("免费模型未返回有效任务编号，请稍后核查。")
            if on_submitted:
                on_submitted(event_id)
            data = None
            try:
                async with client.stream("GET", self.base_url + "/gradio_api/call/infer/" + event_id, headers=headers) as response:
                    check_status(response)
                    event = ""
                    async for line in response.aiter_lines():
                        if line.startswith("event:"):
                            event = line[6:].strip()
                        elif line.startswith("data:") and event == "error":
                            text = line[5:].lower()
                            if "quota" in text or "exceeded" in text:
                                raise ProviderError("免费 GPU 额度已用完，请稍后再试，或配置免费的 Hugging Face 账号 token 增加额度。")
                            raise ProviderError("免费模型当前无法生成，请稍后再试；作品描述已保留。")
                        elif line.startswith("data:") and event == "complete":
                            data = json.loads(line[5:].strip())
                            break
            except (httpx.HTTPError, ValueError) as error:
                raise SubmissionUncertain("免费模型任务已提交，等待结果时连接中断；请稍后核查。") from error
            if not isinstance(data, list) or not data or not isinstance(data[0], dict):
                raise SubmissionUncertain("免费模型没有返回可读取的生成结果。")
            file_url = data[0].get("url")
            if not file_url and isinstance(data[0].get("path"), str):
                file_url = self.base_url + "/gradio_api/file=" + data[0]["path"]
            if not file_url:
                raise ProviderError("免费模型没有返回图片文件。")
            image = await download_image(client, file_url, {urlparse(self.base_url).hostname})
            return ImageResult(image, verify_image(image), "FLUX.1-schnell", event_id, {"seed": data[1] if len(data) > 1 else None, "free_demo": True})
