from .models import QualityReport


async def assess_image(image, interpretation, brief, provider=None):
    if provider is None:
        return QualityReport()
    try:
        report = await provider.inspect(image, interpretation, brief)
        return QualityReport.model_validate(report)
    except Exception:
        return QualityReport(rationale="视觉评估暂时不可用，图片已保存。请检查光影、透视和自然程度。")
