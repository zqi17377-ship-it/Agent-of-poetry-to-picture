import asyncio
import time
import logging
from pydantic import ValidationError
from .literature import analyze_text, design_brief, build_prompt, revise_brief
from .models import Interpretation, VisualBrief, GenerationRequest
from .quality import assess_image
from .providers.base import ProviderError, SubmissionUncertain

logger = logging.getLogger(__name__)


class Workflow:
    def __init__(self, repository, text_provider, image_provider, text_mode="basic", vision_provider=None):
        self.repo, self.text, self.image, self.text_mode, self.vision = repository, text_provider, image_provider, text_mode, vision_provider

    def stage(self, job, stage, external=False):
        current = self.repo.get_job(job.id)
        self.repo.update_job(job.id, stage=stage, call_count=current.call_count + int(external))

    async def run(self, job):
        started = time.monotonic()
        try:
            async with asyncio.timeout(300):
                artwork = self.repo.get_artwork(job.artwork_id)
                if job.operation == "generate":
                    self.stage(job, "analyzing", self.text_mode != "basic")
                    interpretation = await analyze_text(artwork["text"], self.text)
                    self.stage(job, "designing", self.text_mode != "basic")
                    brief = await design_brief(interpretation, self.text)
                else:
                    original = self.repo.get_version(job.source_version_id)
                    interpretation = Interpretation.model_validate(original["interpretation"])
                    self.stage(job, "designing", self.text_mode != "basic")
                    brief = await revise_brief(VisualBrief.model_validate(original["brief"]), job.instruction, self.text)
                prompt = build_prompt(brief)
                self.stage(job, "generating", True)
                reference = self.repo.image_path(job.source_version_id) if job.operation == "edit" else None
                image = await self.image.generate(GenerationRequest(prompt, artwork["aspect_ratio"], reference), on_submitted=lambda event_id: self.repo.update_job(job.id, provider_request_id=event_id))
                self.repo.update_job(job.id, provider_request_id=image.provider_request_id, usage=image.usage or {}, elapsed_ms=int((time.monotonic() - started) * 1000))
                self.stage(job, "checking", self.vision is not None)
                report = await assess_image(image, interpretation, brief, self.vision)
                self.stage(job, "saving")
                self.repo.save_version(job, image.data, {"interpretation": interpretation.model_dump(), "brief": brief.model_dump(), "prompt": prompt, "prompt_version": "2-anchored", "model": image.model, "text_mode": self.text_mode, "usage": image.usage, "quality_report": report.model_dump()})
        except (SubmissionUncertain, TimeoutError):
            self.repo.update_job(job.id, status="needs_review", error="请求已提交或结果不明确，已停止自动重试。请核查生成服务记录后再重新生成。")
        except ProviderError as error:
            self.repo.update_job(job.id, status="failed", error=str(error))
        except (ValidationError, ValueError):
            self.repo.update_job(job.id, status="failed", error="文学理解或画面描述格式不完整，原文已保留，可重试或检查模型配置。")
        except asyncio.CancelledError:
            self.repo.update_job(job.id, status="needs_review", error="运行已中断，原文和已有版本已保留。请核查后重新生成。")
            raise
        except Exception as error:
            # Exception messages may contain credentials or provider response
            # bodies. Record the job and failure type, never raw provider data.
            logger.error("Job %s failed unexpectedly (%s)", job.id, type(error).__name__)
            self.repo.update_job(job.id, status="needs_review", error="处理过程中出现异常，已保留任务。请查看运行日志并核查生成状态。")
        finally:
            self.repo.update_job(job.id, elapsed_ms=int((time.monotonic() - started) * 1000))
