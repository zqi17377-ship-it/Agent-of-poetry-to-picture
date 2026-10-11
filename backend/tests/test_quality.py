import asyncio
from backend.app.quality import assess_image
from backend.app.models import QualityReport


class BrokenEvaluator:
    async def inspect(self, *args):
        raise RuntimeError("unavailable")


class FlagsEvaluator:
    async def inspect(self, *args):
        return {"flags": ["水面纹理需检查"], "rationale": "需要人工查看"}


def test_assessment_failure_preserves_a_usable_report():
    result = asyncio.run(assess_image(None, None, None, BrokenEvaluator()))
    assert isinstance(result, QualityReport)
    assert "图片已保存" in result.rationale


def test_assessment_reports_flags_without_regeneration():
    result = asyncio.run(assess_image(None, None, None, FlagsEvaluator()))
    assert result.flags == ["水面纹理需检查"]
