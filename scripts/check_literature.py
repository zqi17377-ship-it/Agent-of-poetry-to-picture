"""Exercise real local understanding without requesting or paying for any image."""
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.config import Settings
from backend.app.providers.factory import create_providers
from backend.app.literature import analyze_text, design_brief, build_prompt

SAMPLES = [
    # User-supplied failing text: regression, not an assertion of author/source.
    ("user-metaphor", "我如何用时光之羽，刻画在永恒之台阶上，爬上爬下的细节吗？"),
    # Original calibration samples; do not present these as Adonis poems.
    ("garden", "孤独在我的花园里生长。围墙外的城市睡了，墙内仍有一朵花醒着。"),
    ("warmth", "窗上的晨光把长夜慢慢缝合。桌上的茶还热着，我开始相信今天。"),
]


async def main():
    settings = Settings.from_env()
    settings.text_provider = "local"
    provider, _ = create_providers(settings)
    reports = []
    try:
        for name, text in SAMPLES:
            if len(sys.argv) > 1 and name != sys.argv[1]:
                continue
            started = time.monotonic()
            print(f"Understanding: {name}", flush=True)
            interpretation = await analyze_text(text, provider)
            print(f"Interpretation ready after {time.monotonic() - started:.1f}s", flush=True)
            brief = await design_brief(interpretation, provider)
            reports.append({"sample": name, "interpretation": interpretation.model_dump(),
                            "brief": brief.model_dump(), "prompt": build_prompt(brief),
                            "elapsed_seconds": round(time.monotonic() - started, 1), "last_usage": provider.last_usage})
            output = ROOT / "data" / "local-literature-check.json"
            output.parent.mkdir(exist_ok=True)
            output.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(reports[-1], ensure_ascii=False), flush=True)
    finally:
        await provider.close()
    output = ROOT / "data" / "local-literature-check.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Saved data/local-literature-check.json; no image requested.", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
