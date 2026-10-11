import asyncio
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.config import Settings
from backend.app.providers.basic import BasicTextProvider
from backend.tests.test_jobs import ImageFixture


def client_for(tmp_path):
    app = create_app(Settings(data_dir=tmp_path), BasicTextProvider(), ImageFixture(), start_worker=False)
    return TestClient(app)


def test_create_returns_job_and_history_without_exposing_keys(tmp_path):
    with client_for(tmp_path) as client:
        result = client.post("/api/artworks", json={"text": "a quiet lake"})
        assert result.status_code == 202
        ids = result.json()
        job = client.get("/api/jobs/" + ids["job_id"]).json()
        assert job["status"] == "queued"
        assert client.get("/api/artworks").json()[0]["id"] == ids["artwork_id"]
        assert "api_key" not in client.get("/api/config").text


def test_invalid_poem_and_missing_image_have_clear_status(tmp_path):
    with client_for(tmp_path) as client:
        for text in ["  ", "a" * 8001]:
            assert client.post("/api/artworks", json={"text": text}).status_code == 422
        assert client.get("/api/versions/missing/image").status_code == 404
        assert client.get("/api/jobs/missing").status_code == 404


def test_generated_image_downloads_and_unsupported_edit_is_explicit(tmp_path):
    with client_for(tmp_path) as client:
        ids = client.post("/api/artworks", json={"text": "a quiet lake"}).json()
        asyncio.run(client.app.state.workflow.run(client.app.state.repo.claim()))
        artwork = client.get("/api/artworks/" + ids["artwork_id"]).json()
        version_id = artwork["versions"][0]["id"]
        response = client.get("/api/versions/" + version_id + "/image?download=true")
        assert response.content.startswith(b"\x89PNG")
        assert "attachment" in response.headers["content-disposition"]
        revision = {"source_version_id": version_id, "instruction": "less fog"}
        assert client.post("/api/artworks/" + ids["artwork_id"] + "/revisions", json=revision).status_code == 409
        revision["mode"] = "regenerate"
        assert client.post("/api/artworks/" + ids["artwork_id"] + "/revisions", json=revision).status_code == 202


def test_browser_cross_origin_write_is_rejected(tmp_path):
    with client_for(tmp_path) as client:
        result = client.post("/api/artworks", json={"text": "lake"}, headers={"Origin": "https://untrusted.example"})
        assert result.status_code == 403
