import asyncio
import json
import httpx
import pytest
import os
import subprocess
import sys
import re
from backend.app.models import VisualBrief
from backend.app.providers.windows_job import OwnedProcessJob
from backend.app.providers.local_text import LocalTextProvider, LocalModelRuntime
from backend.app.providers.base import ProviderError


class RuntimeFixture:
    base_url = "http://127.0.0.1:12345/v1"
    key = "ephemeral-local-key"
    async def start(self):
        pass


def test_local_model_gets_schema_and_bounded_non_thinking_request():
    def handler(request):
        assert request.url.host == "127.0.0.1"
        assert request.headers["authorization"] == "Bearer ephemeral-local-key"
        body = json.loads(request.content)
        assert body["max_tokens"] <= 1600
        assert body["chat_template_kwargs"]["enable_thinking"] is False
        assert body["response_format"]["schema"]["type"] == "object"
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": '{"meaning":"羽毛与台阶"}'}}]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await LocalTextProvider(RuntimeFixture(), client).complete_json("system", "text", {"type": "object"})
    assert asyncio.run(run())["meaning"] == "羽毛与台阶"


def test_missing_local_weights_fail_with_setup_instruction(tmp_path):
    runtime = LocalModelRuntime(tmp_path / "missing.exe", tmp_path / "missing.gguf")
    with pytest.raises(ProviderError, match="setup_local_text"):
        asyncio.run(runtime.start())
    assert runtime.process is None


def test_generation_grammar_keeps_quotes_and_unbounded_strings_out_of_fields():
    def handler(request):
        schema = json.loads(request.content)["response_format"]["schema"]
        english = schema["properties"]["subject"]["pattern"]
        chinese = schema["properties"]["rationale"]["pattern"]
        assert re.fullmatch(english, "a cup of tea")
        assert not re.fullmatch(english, 'tea " cup')
        assert not re.fullmatch(english, "tea\tcup")
        assert not re.fullmatch(english, "晨光")
        assert not re.fullmatch(english, "a" * 201)
        assert re.fullmatch(chinese, "晨光让长夜成为过去。")
        assert not re.fullmatch(chinese, '晨光"}')
        assert schema["additionalProperties"] is False
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await LocalTextProvider(RuntimeFixture(), client).complete_json("system", "text", VisualBrief.model_json_schema())
    asyncio.run(run())


def test_truncated_local_json_is_not_used_for_image_prompt():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await LocalTextProvider(RuntimeFixture(), client).complete_json("system", "text", {"type": "object"})
    with pytest.raises(ProviderError, match="过长"):
        asyncio.run(run())


@pytest.mark.skipif(os.name != "nt", reason="Windows process lifetime")
def test_windows_job_closing_terminates_only_our_child():
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        job = OwnedProcessJob(child.pid)
        assert child.poll() is None
        job.close()
        child.wait(timeout=5)  # KILL_ON_JOB_CLOSE can report exit code zero on Windows.
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
