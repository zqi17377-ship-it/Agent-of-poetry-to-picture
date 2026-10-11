"""Install pinned official Qwen weights and llama.cpp CPU runtime (Windows x64)."""
import hashlib
import os
import time
import zipfile
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
MODEL = "Qwen3-4B-Q4_K_M.gguf"
MODEL_SHA = "7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5"
MODEL_REV = "bc640142c66e1fdd12af0bd68f40445458f3869b"
RUNTIME_SHA = "f1fe2ec55a80eabb525bc7334579327ea993a03d10cea9a8175971b57eb9c98b"
RUNTIME_URL = "https://github.com/ggml-org/llama.cpp/releases/download/b10025/llama-b10025-bin-win-cpu-x64.zip"


def sha256(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def download(url, target, expected):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and sha256(target) == expected:
        print(f"Already verified: {target.name}", flush=True)
        return
    partial = target.with_suffix(target.suffix + ".part")
    for attempt in range(5):
        offset = partial.stat().st_size if partial.exists() else 0
        try:
            with httpx.stream("GET", url, headers={"Range": f"bytes={offset}-"} if offset else {},
                              follow_redirects=True, timeout=90) as response:
                response.raise_for_status()
                if response.status_code != 206:
                    offset = 0
                total = offset + int(response.headers.get("content-length", 0))
                last = time.monotonic()
                with partial.open("ab" if offset else "wb") as output:
                    for chunk in response.iter_bytes(1024 * 1024):
                        output.write(chunk)
                        offset += len(chunk)
                        if time.monotonic() - last > 15:
                            print(f"{target.name}: {offset // 1048576} / {total // 1048576} MB", flush=True)
                            last = time.monotonic()
            if sha256(partial) != expected:
                partial.unlink()
                raise RuntimeError("Download checksum mismatch")
            os.replace(partial, target)
            print(f"Verified SHA256: {target.name}", flush=True)
            return
        except httpx.HTTPError:
            print(f"Download interrupted; resume attempt {attempt + 1}/5", flush=True)
            time.sleep(2)
    raise RuntimeError("Download failed; run this script again to resume")


def main():
    archive = ROOT / ".tmp" / "llama-b10025-win-cpu-x64.zip"
    download(RUNTIME_URL, archive, RUNTIME_SHA)
    destination = ROOT / "runtime" / "llama"
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        for entry in bundle.infolist():
            if not (destination / entry.filename).resolve().is_relative_to(destination.resolve()):
                raise RuntimeError("Unsafe archive path")
        bundle.extractall(destination)
    download(f"https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/{MODEL_REV}/{MODEL}",
             ROOT / "models" / MODEL, MODEL_SHA)
    print("Local text model installed. Set TEXT_PROVIDER=local and restart the app.", flush=True)


if __name__ == "__main__":
    main()
