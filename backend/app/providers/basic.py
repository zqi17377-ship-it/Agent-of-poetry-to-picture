"""An explicit, limited keyword fallback, not a language model."""
import json
import re
from .base import ProviderError

SCENES = [
    ("snow-covered landscape", ["snow", "winter", "雪", "冬"]),
    ("quiet sea shoreline", ["sea", "ocean", "waves", "海", "浪"]),
    ("still lakeshore", ["lake", "湖"]),
    ("riverbank", ["river", "stream", "河", "溪"]),
    ("woodland", ["forest", "woods", "trees", "森林", "树林", "树"]),
    ("mountain landscape", ["mountain", "山"]),
    ("quiet city street", ["street", "city", "街", "城市"]),
    ("open meadow", ["grass", "field", "meadow", "草", "田野"]),
]
MOODS = [("悲伤", ["grief", "sorrow", "tears", "悲", "泪"]), ("孤独", ["alone", "lonely", "loneliness", "孤独", "独自"]), ("温暖", ["warm", "joy", "sunlight", "温暖", "欢乐", "阳光"])]


def matched_quote(text: str, keywords: list[str]) -> str | None:
    for word in keywords:
        pattern = re.escape(word) if not word.isascii() else r"\b" + re.escape(word) + r"\b"
        result = re.search(pattern, text, re.I)
        if result:
            return result.group()
    return None


class BasicTextProvider:
    async def complete_json(self, system: str, content: str, schema: dict) -> dict:
        if schema.get("title") == "Interpretation":
            imagery = []
            for image, keywords in SCENES:
                quote = matched_quote(content, keywords)
                if quote:
                    imagery.append({"image": image, "source_quote": quote})
            emotions = [name for name, words in MOODS if matched_quote(content, words)]
            if not imagery:
                raise ProviderError("基础解析器无法理解这段诗的意象，请启用本机语言模型或配置文字 API 后重试；尚未请求出图。")
            return {"language": "zh" if re.search(r"[\u4e00-\u9fff]", content) else "en", "emotions": emotions or ["平静（默认创作方向）"], "imagery": imagery, "ambiguities": ["当前使用基础关键词提取，无法可靠理解隐喻及复杂文学情绪；可接入语言模型提升理解。"]}
        payload = json.loads(content)
        if "current" in payload:
            # Preserve the brief; pass the user's visual instruction to the image model.
            result = dict(payload["current"])
            result["requested_adjustment"] = "\n".join(filter(None, [result.get("requested_adjustment", ""), payload["revision"]]))
            result["rationale"] = "保留已有画面描述，并将你的调整要求交给图像模型。"
            return result
        warm = "温暖" in payload.get("emotions", [])
        text = payload.get("source_text", "")
        subject = ", ".join(item["image"] for item in payload.get("imagery", [])) or "quiet open landscape"
        night = bool(matched_quote(text, ["night", "moon", "夜", "月"])); rain = bool(matched_quote(text, ["rain", "雨"]))
        return {
            "subject": subject,
            "setting": "a plausible everyday landscape, no invented landmarks or people" + (", light rainfall" if rain else ""),
            "composition": "restrained wide view, natural horizon, negative space, a feeling of " + ("warmth" if warm else "quiet and distance"),
            "lighting": "natural moonlit night, realistic dim exposure" if night else ("gentle warm sunlight" if warm else "soft overcast daylight"),
            "palette": "warm highlights with cool natural shadows" if warm else "muted blue-grey and natural greens, no strong blue filter",
            "rendering": "natural landscape photography, believable textures, subtle depth, low-to-medium saturation",
            "additions": ["构图、光线和空间关系为创作补充；基础模式不能完整解读原文。"],
            "rationale": "根据原文可识别的意象安排画面，并采用自然写实的光线。当前为基础理解模式，可接入语言模型进一步理解诗意。",
            "anchors": [{"source_quote": item["source_quote"], "visual_element": item["image"], "connection": "原文中直接出现的风景意象（基础关键词模式）"} for item in payload.get("imagery", [])],
        }
