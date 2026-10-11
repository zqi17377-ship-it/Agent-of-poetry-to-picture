"""One real free image request. No accounts are created or charges enabled."""
import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.config import Settings
from backend.app.providers.factory import create_providers
from backend.app.models import GenerationRequest
from backend.app.literature import analyze_text, design_brief, build_prompt


async def main():
    settings = Settings.from_env()
    if settings.image_provider != "hf_space" or settings.text_provider != "basic":
        raise SystemExit("Free smoke test requires IMAGE_PROVIDER=hf_space and TEXT_PROVIDER=basic.")
    text, image = create_providers(settings)
    poem = "The rain has left the lake.\nUnder the grey sky, the water holds the silence of the shore."
    print("Analyzing original debugging text", flush=True)
    meaning = await analyze_text(poem, text)
    brief = await design_brief(meaning, text)
    print("Submitting one free FLUX generation", flush=True)
    async with asyncio.timeout(280):
        result = await image.generate(GenerationRequest(build_prompt(brief)), on_submitted=lambda event: print("Submitted event: " + event, flush=True))
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}[result.mime_type]
    output = settings.data_dir / ("smoke-flux" + suffix)
    output.write_bytes(result.data)
    (settings.data_dir / "smoke-flux.json").write_text(json.dumps({"text": poem, "brief": brief.model_dump(), "model": result.model, "usage": result.usage, "request_id": result.provider_request_id}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Saved generated image: " + str(output), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
