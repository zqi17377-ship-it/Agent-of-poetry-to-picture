import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    data_dir: Path = ROOT / "data"
    image_provider: str = "hf_space"
    text_provider: str = "basic"
    hf_space_url: str = "https://black-forest-labs-flux-1-schnell.hf.space"
    hf_token: str = ""
    gemini_api_key: str = ""
    gemini_text_model: str = "gemini-2.5-flash"
    gemini_image_model: str = "gemini-nano-banana-2.1"
    text_base_url: str = ""
    text_api_key: str = ""
    text_model: str = ""
    image_base_url: str = ""
    image_api_key: str = ""
    image_model: str = ""
    image_allowed_hosts: str = ""

    @classmethod
    def from_env(cls):
        load_dotenv(ROOT / ".env", override=False)
        result = cls()
        for name in cls.__dataclass_fields__:
            value = os.getenv(name.upper())
            if value is not None:
                setattr(result, name, Path(value).resolve() if name == "data_dir" else value.strip())
        if result.image_provider not in {"hf_space", "gemini", "compatible"} or result.text_provider not in {"basic", "gemini", "compatible"}:
            raise ValueError("不支持的模型配置，请查看 .env.example。")
        return result
