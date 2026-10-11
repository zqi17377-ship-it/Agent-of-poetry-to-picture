import base64
import io
from contextlib import asynccontextmanager
from urllib.parse import urlparse
import httpx
from PIL import Image
from .base import ProviderError, SubmissionUncertain

MAX_IMAGE_BYTES = 30 * 1024 * 1024


@asynccontextmanager
async def client_context(client: httpx.AsyncClient | None):
    if client is not None:
        yield client
    else:
        async with httpx.AsyncClient(timeout=httpx.Timeout(240, connect=20), follow_redirects=False) as created:
            yield created


async def post_json(client, url: str, body: dict, headers: dict) -> dict:
    try:
        response = await client.post(url, json=body, headers=headers)
    except httpx.ConnectError as error:
        raise ProviderError("无法连接模型服务，请检查网络后重试。") from error
    except (httpx.TimeoutException, httpx.NetworkError) as error:
        raise SubmissionUncertain("请求结果尚不明确，已停止自动重试。请检查服务记录后再重新生成。") from error
    check_status(response)
    try:
        return response.json()
    except ValueError as error:
        raise SubmissionUncertain("模型服务响应格式不正确，已保留任务供核查。") from error


def check_status(response):
    if response.status_code < 400:
        return
    messages = {401: "模型服务认证失败，请检查接入密钥。", 403: "模型服务拒绝访问，请检查账号权限或地区可用性。", 404: "模型或接口不存在，请检查模型名称及服务地址。", 429: "模型服务额度不足或请求过于频繁，请稍后再试。"}
    if response.status_code >= 500:
        raise SubmissionUncertain("模型服务暂时异常，请核查请求状态后再试。")
    raise ProviderError(messages.get(response.status_code, "模型服务未接受请求，请检查接入配置和支持的图片尺寸。"))


def decode_image(value: str) -> bytes:
    if len(value) > MAX_IMAGE_BYTES * 1.4:
        raise ProviderError("模型返回的图片过大。")
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as error:
        raise ProviderError("模型未返回有效的图片数据。") from error


def verify_image(data: bytes) -> str:
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ProviderError("模型未返回有效大小的图片。")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > 24_000_000 or image.format not in {"PNG", "JPEG", "WEBP"}:
                raise ProviderError("模型返回了不支持的图片格式或尺寸。")
            mime = Image.MIME[image.format]
            image.verify()
            return mime
    except ProviderError:
        raise
    except Exception as error:
        raise ProviderError("模型返回的文件不是可读取的图片。") from error


async def download_image(client, url: str, allowed_hosts: set[str], headers: dict | None = None) -> bytes:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in allowed_hosts or parsed.username or parsed.password:
        raise ProviderError("图片下载地址不在允许的服务范围内，请检查 IMAGE_ALLOWED_HOSTS 配置。")
    try:
        # Never forward API credentials to file/CDN endpoints.
        async with client.stream("GET", url, headers=headers or {}) as response:
            check_status(response)
            if response.status_code >= 300:
                raise ProviderError("图片下载发生跳转，请配置返回原图的服务地址。")
            chunks, size = [], 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > MAX_IMAGE_BYTES:
                    raise ProviderError("模型返回的图片过大。")
                chunks.append(chunk)
            return b"".join(chunks)
    except httpx.HTTPError as error:
        raise SubmissionUncertain("图片已提交生成，但下载没有完成，请核查服务记录。") from error
