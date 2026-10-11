"""Owned loopback llama.cpp server; no paid text API or account required."""
import asyncio
import json
import copy
import os
import secrets
import socket
import subprocess
import time
from pathlib import Path
import httpx
from .base import ProviderError, SubmissionUncertain
from .http_utils import post_json
from .windows_job import OwnedProcessJob


class LocalModelRuntime:
    def __init__(self, binary: Path, model: Path):
        self.binary, self.model = Path(binary), Path(model)
        self.process = None
        self.job = None
        self.base_url = ""
        self.key = secrets.token_urlsafe(32)
        self.lock = asyncio.Lock()

    async def start(self):
        async with self.lock:
            if self.process is not None and self.process.returncode is None:
                return
            if self.job is not None:
                self.job.close()
                self.job = None
            if not self.binary.is_file() or not self.model.is_file():
                raise ProviderError("本机文学模型尚未安装，请运行 安装文学模型.cmd（scripts/setup_local_text.py），约下载 2.5GB，然后重试。")
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
            self.base_url = f"http://127.0.0.1:{port}/v1"
            # Do not pass the app's HF/API credentials to the model process.
            env = {name: value for name, value in os.environ.items() if name.upper() in
                   {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "COMSPEC"}}
            env["LLAMA_API_KEY"] = self.key
            command = [str(self.binary), "--model", str(self.model), "--alias", "local-literature",
                       "--host", "127.0.0.1", "--port", str(port), "--ctx-size", "16384",
                       "--parallel", "1", "--threads", "6", "--threads-batch", "8",
                       "--n-gpu-layers", "0", "--poll", "0", "--prio", "-1", "--jinja",
                       "--reasoning", "off", "--log-disable"]
            try:
                self.process = await asyncio.create_subprocess_exec(
                    *command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                self.job = OwnedProcessJob(self.process.pid)
                deadline = time.monotonic() + 60
                async with httpx.AsyncClient(timeout=2, trust_env=False) as client:
                    while time.monotonic() < deadline:
                        if self.process.returncode is not None:
                            raise ProviderError("本机文学模型启动失败，请检查模型文件及运行程序。")
                        try:
                            response = await client.get(f"http://127.0.0.1:{port}/health", headers={"Authorization": "Bearer " + self.key})
                            if response.status_code == 200:
                                return
                        except httpx.HTTPError:
                            pass
                        await asyncio.sleep(0.5)
                raise ProviderError("本机文学模型加载超时，尚未请求出图。请关闭占用内存较多的程序后重试。")
            except BaseException:
                await self.close()
                raise

    async def close(self):
        # Only terminate the exact child process we created, never a process found by port/name.
        process, self.process = self.process, None
        if self.job is not None:
            self.job.close()
            self.job = None
        if process is not None and process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                return
            try:
                await asyncio.wait_for(process.wait(), 5)
            except TimeoutError:
                process.kill()
                await process.wait()


class LocalTextProvider:
    def __init__(self, runtime: LocalModelRuntime, client=None):
        self.runtime, self.client = runtime, client
        self.last_usage = None

    async def complete_json(self, system, content, schema):
        await self.runtime.start()
        schema = copy.deepcopy(schema)
        if schema.get("title") == "VisualBrief":
            schema["properties"].pop("requested_adjustment", None)
            # The model otherwise switches every field to English once image fields
            # are constrained. Keep explanations readable for the Chinese UI.
            # llama.cpp's pattern converter copies regex classes directly into
            # its grammar and ignores maxLength when pattern is present. Bare
            # .* accepts unescaped JSON quotes and can consume the whole object.
            # Bound each regex and exclude quotes, backslashes and line breaks.
            def chinese(limit):
                return rf'^[㐀-鿿][^"\\\x00-\x1f]{{0,{limit - 1}}}$'
            def english(limit):
                return rf'^[^㐀-鿿"\\\x00-\x1f]{{1,{limit}}}$'
            schema["properties"]["rationale"]["pattern"] = chinese(200)
            schema["properties"]["additions"]["items"]["pattern"] = chinese(100)
            schema["$defs"]["VisualAnchor"]["properties"]["connection"]["pattern"] = chinese(120)
            for name in ["subject", "setting", "composition", "lighting", "palette", "rendering"]:
                schema["properties"][name]["pattern"] = english(schema["properties"][name]["maxLength"])
            schema["$defs"]["VisualAnchor"]["properties"]["visual_element"]["pattern"] = english(220)
            schema["properties"]["rationale"]["maxLength"] = 200
            schema["properties"]["additions"]["maxItems"] = 3
            schema["properties"]["additions"]["items"]["maxLength"] = 100
            anchor = schema["$defs"]["VisualAnchor"]["properties"]
            anchor["visual_element"]["maxLength"] = 220
            anchor["connection"]["maxLength"] = 120
            schema["required"] = list(dict.fromkeys([*schema.get("required", []), "anchors"]))
        elif schema.get("title") == "Interpretation":
            schema["properties"]["imagery"]["maxItems"] = 6
            for name in ["emotions", "ambiguities", "relations"]:
                schema["properties"][name]["maxItems"] = 6
                schema["properties"][name]["items"]["maxLength"] = 150
            schema["required"] = list(dict.fromkeys([*schema.get("required", []), "relations"]))
        def restrict_objects(node):
            if isinstance(node, dict):
                if node.get("type") == "object" and "properties" in node:
                    node["additionalProperties"] = False
                for value in node.values():
                    restrict_objects(value)
            elif isinstance(node, list):
                for value in node:
                    restrict_objects(value)
        restrict_objects(schema)
        body = {"model": "local-literature", "messages": [
            {"role": "system", "content": system + "\nRequired JSON schema: " + json.dumps(schema, ensure_ascii=False)},
            {"role": "user", "content": content}],
            "response_format": {"type": "json_object", "schema": schema},
            "chat_template_kwargs": {"enable_thinking": False}, "max_tokens": 1200,
            "temperature": 0.7, "top_p": 0.8, "top_k": 20, "min_p": 0.0, "presence_penalty": 1.0}
        async def request(client):
            try:
                return await post_json(client, self.runtime.base_url + "/chat/completions", body,
                                       {"Authorization": "Bearer " + self.runtime.key})
            except SubmissionUncertain as error:
                raise ProviderError("本机文学理解没有完成，尚未请求出图。请缩短诗文后重试。") from error
        if self.client is not None:
            result = await request(self.client)
        else:
            async with httpx.AsyncClient(timeout=180, trust_env=False) as client:
                result = await request(client)
        self.last_usage = result.get("usage")
        try:
            choice = result["choices"][0]
            if choice.get("finish_reason") == "length":
                raise ProviderError("文学模型输出过长，已停止出图。请缩短诗文后重试。")
            return json.loads(choice["message"]["content"])
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise ProviderError("本机文学模型返回格式不完整，已停止出图。") from error

    async def close(self):
        await self.runtime.close()
