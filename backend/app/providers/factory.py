from ..config import Settings
from .basic import BasicTextProvider
from .gemini import GeminiProvider
from .hf_space import HuggingFaceSpaceProvider
from .compatible import CompatibleProvider
from .local_text import LocalTextProvider, LocalModelRuntime


def create_providers(settings: Settings):
    gemini = GeminiProvider(settings.gemini_api_key, settings.gemini_text_model, settings.gemini_image_model)
    if settings.text_provider == "local":
        text = LocalTextProvider(LocalModelRuntime(settings.local_text_binary, settings.local_text_model))
    elif settings.text_provider == "basic":
        text = BasicTextProvider()
    elif settings.text_provider == "gemini":
        text = gemini
    else:
        text = CompatibleProvider(settings.text_base_url, settings.text_api_key, settings.text_model)
    if settings.image_provider == "hf_space":
        image = HuggingFaceSpaceProvider(settings.hf_space_url, settings.hf_token)
    elif settings.image_provider == "gemini":
        image = gemini
    else:
        image = CompatibleProvider(settings.image_base_url, settings.image_api_key, settings.image_model, settings.image_allowed_hosts)
    return text, image
