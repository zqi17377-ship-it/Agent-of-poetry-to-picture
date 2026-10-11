import asyncio
import base64
import io
import json
import httpx
import pytest
from PIL import Image
from backend.app.models import GenerationRequest
from backend.app.providers.hf_space import HuggingFaceSpaceProvider
from backend.app.providers.gemini import GeminiProvider
from backend.app.providers.compatible import CompatibleProvider
from backend.app.providers.base import ProviderError, SubmissionUncertain


def png_bytes():
    output = io.BytesIO()
    Image.new("RGB", (12, 8), "#8899aa").save(output, "PNG")
    return output.getvalue()


def run_provider(provider_type, handler, *args, **kwargs):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = provider_type(*args, client=client, **kwargs)
            return await provider.generate(GenerationRequest("natural quiet lake"))
    return asyncio.run(run())


def test_hf_space_retrieves_real_generated_file_from_sse():
    def handler(request):
        if request.method == "POST":
            body = json.loads(request.content)
            assert body["data"][3:5] == [768, 512]
            return httpx.Response(200, json={"event_id": "event123"})
        if request.url.path.endswith("event123"):
            return httpx.Response(200, text='event: complete\ndata: [{"url":"https://test.hf.space/gradio_api/file=/tmp/x.png"},42]\n\n')
        return httpx.Response(200, content=png_bytes(), headers={"content-type": "image/png"})
    result = run_provider(HuggingFaceSpaceProvider, handler, "https://test.hf.space")
    assert result.data == png_bytes()
    assert result.provider_request_id == "event123"
    assert result.model == "FLUX.1-schnell"


def test_hf_quota_is_visible_and_does_not_return_fake_image():
    def handler(request):
        return httpx.Response(200, json={"event_id": "123"}) if request.method == "POST" else httpx.Response(200, text='event: error\ndata: ["You have exceeded your GPU quota"]\n\n')
    with pytest.raises(ProviderError, match="额度"):
        run_provider(HuggingFaceSpaceProvider, handler, "https://test.hf.space")


def test_hf_rejects_unexpected_download_host():
    def handler(request):
        return httpx.Response(200, json={"event_id": "123"}) if request.method == "POST" else httpx.Response(200, text='event: complete\ndata: [{"url":"http://127.0.0.1/private"},42]\n\n')
    with pytest.raises(ProviderError):
        run_provider(HuggingFaceSpaceProvider, handler, "https://test.hf.space")


def test_timeout_is_uncertain_and_never_automatically_retried():
    requests = []
    def handler(request):
        requests.append(request)
        raise httpx.ReadTimeout("secret token must not appear", request=request)
    with pytest.raises(SubmissionUncertain) as error:
        run_provider(HuggingFaceSpaceProvider, handler, "https://test.hf.space")
    assert len(requests) == 1
    assert "secret" not in str(error.value)


def test_gemini_decodes_base64_and_sends_reference_image(tmp_path):
    reference = tmp_path / "ref.png"
    reference.write_bytes(png_bytes())
    def handler(request):
        body = json.loads(request.content)
        assert body["contents"][0]["parts"][1]["inlineData"]["mimeType"] == "image/png"
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "image/png", "data": base64.b64encode(png_bytes()).decode()}}]}}], "usageMetadata": {"totalTokenCount": 12}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await GeminiProvider("test-key", client=client).generate(GenerationRequest("lake", reference_path=reference))
    result = asyncio.run(run())
    assert result.data == png_bytes()
    assert result.usage == {"totalTokenCount": 12}


def test_compatible_uses_configured_base_url_and_model():
    def handler(request):
        assert str(request.url) == "https://example.test/v1/images/generations"
        assert json.loads(request.content)["model"] == "custom-flux"
        assert request.headers["authorization"] == "Bearer local-key"
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(png_bytes()).decode()}]})
    result = run_provider(CompatibleProvider, handler, "https://example.test/v1", "local-key", "custom-flux")
    assert result.data == png_bytes()


def test_provider_error_does_not_leak_upstream_secrets():
    def handler(request):
        return httpx.Response(401, json={"error": {"message": "bad secret-key-123"}})
    with pytest.raises(ProviderError) as error:
        run_provider(CompatibleProvider, handler, "https://example.test/v1", "secret-key-123", "flux")
    assert "secret-key-123" not in str(error.value)
