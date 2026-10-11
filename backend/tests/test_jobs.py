import asyncio
import io
import pytest
from PIL import Image
from backend.app.models import ArtworkInput, ImageResult
from backend.app.storage import Repository
from backend.app.workflow import Workflow
from backend.app.providers.basic import BasicTextProvider
from backend.app.providers.base import SubmissionUncertain, ProviderError


class ImageFixture:
    supports_edit = False
    def __init__(self, error=None):
        self.error = error
        self.requests = []

    async def generate(self, request, on_submitted=None):
        self.requests.append(request)
        if on_submitted:
            on_submitted("external-123")
        if self.error:
            raise self.error
        image = io.BytesIO()
        Image.new("RGB", (12, 8), "#8899aa").save(image, "PNG")
        return ImageResult(image.getvalue(), "image/png", "fixture", "external-123", {"images": 1})


def setup_job(tmp_path):
    repo = Repository(tmp_path)
    artwork_id, job_id = repo.create_artwork(ArtworkInput(text="The lake is quiet, and I am alone."))
    return repo, artwork_id, job_id


def test_success_saves_original_bytes_version_and_usage(tmp_path):
    repo, artwork_id, job_id = setup_job(tmp_path)
    provider = ImageFixture()
    asyncio.run(Workflow(repo, BasicTextProvider(), provider, "basic").run(repo.claim()))
    job = repo.get_job(job_id)
    assert job.status == "succeeded"
    assert job.call_count == 1
    assert job.provider_request_id == "external-123"
    artwork = repo.get_artwork(artwork_id)
    assert len(artwork["versions"]) == 1
    version = artwork["versions"][0]
    assert repo.image_path(version["id"]).read_bytes().startswith(b"\x89PNG")
    assert version["usage"] == {"images": 1}
    assert "lake" in provider.requests[0].prompt


def test_uncertain_request_is_preserved_and_not_retried(tmp_path):
    repo, _, job_id = setup_job(tmp_path)
    provider = ImageFixture(SubmissionUncertain("timeout"))
    asyncio.run(Workflow(repo, BasicTextProvider(), provider, "basic").run(repo.claim()))
    assert repo.get_job(job_id).status == "needs_review"
    assert repo.get_job(job_id).provider_request_id == "external-123"
    assert len(provider.requests) == 1
    assert repo.claim() is None


def test_explicit_quota_error_fails_without_new_generation(tmp_path):
    repo, _, job_id = setup_job(tmp_path)
    provider = ImageFixture(ProviderError("额度不足"))
    asyncio.run(Workflow(repo, BasicTextProvider(), provider, "basic").run(repo.claim()))
    assert repo.get_job(job_id).status == "failed"
    assert "额度" in repo.get_job(job_id).error
    assert len(provider.requests) == 1


def test_restart_keeps_queued_and_marks_running_for_review(tmp_path):
    repo, _, running_id = setup_job(tmp_path)
    repo.claim()
    _, queued_id = repo.create_artwork(ArtworkInput(text="another poem"))
    restarted = Repository(tmp_path)
    restarted.recover_running()
    assert restarted.get_job(running_id).status == "needs_review"
    assert restarted.get_job(queued_id).status == "queued"


def test_only_one_running_job_can_be_claimed(tmp_path):
    repo, _, _ = setup_job(tmp_path)
    repo.create_artwork(ArtworkInput(text="another poem"))
    assert repo.claim() is not None
    assert Repository(tmp_path).claim() is None


def test_regeneration_preserves_parent_and_original_image(tmp_path):
    repo, artwork_id, _ = setup_job(tmp_path)
    workflow = Workflow(repo, BasicTextProvider(), ImageFixture(), "basic")
    asyncio.run(workflow.run(repo.claim()))
    original = repo.get_artwork(artwork_id)["versions"][0]
    repo.create_revision(artwork_id, original["id"], "less mist", "regenerate")
    asyncio.run(workflow.run(repo.claim()))
    versions = repo.get_artwork(artwork_id)["versions"]
    assert len(versions) == 2
    assert versions[1]["parent_version_id"] == original["id"]
    assert versions[1]["revision_text"] == "less mist"
    assert repo.image_path(original["id"]).exists()


def test_revision_cannot_use_another_artworks_image(tmp_path):
    repo, artwork_id, _ = setup_job(tmp_path)
    asyncio.run(Workflow(repo, BasicTextProvider(), ImageFixture(), "basic").run(repo.claim()))
    version = repo.get_artwork(artwork_id)["versions"][0]
    another, _ = repo.create_artwork(ArtworkInput(text="river"))
    with pytest.raises(ValueError):
        repo.create_revision(another, version["id"], "mist", "regenerate")


def test_worker_lease_prevents_second_process_from_recovering_live_jobs(tmp_path):
    repo, _, job_id = setup_job(tmp_path)
    assert repo.acquire_lease("worker-a")
    repo.claim()
    other = Repository(tmp_path)
    assert not other.acquire_lease("worker-b")
    assert repo.get_job(job_id).status == "running"
    repo.release_lease("worker-a")
    assert other.acquire_lease("worker-b")
