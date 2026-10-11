from contextlib import asynccontextmanager
from dataclasses import asdict
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .config import Settings, ROOT
from .models import ArtworkInput, RevisionInput
from .providers.factory import create_providers
from .storage import Repository
from .workflow import Workflow
from .worker import Worker


def create_app(settings=None, text_provider=None, image_provider=None, start_worker=True):
    settings = settings or Settings.from_env()
    if text_provider is None or image_provider is None:
        text_provider, image_provider = create_providers(settings)
    repo = Repository(settings.data_dir)
    workflow = Workflow(repo, text_provider, image_provider, settings.text_provider)
    worker = Worker(repo, workflow)

    @asynccontextmanager
    async def lifespan(app):
        if start_worker:
            await worker.start()
        try:
            yield
        finally:
            if start_worker:
                await worker.stop()

    app = FastAPI(title="余境 · 诗文意境图", lifespan=lifespan)
    app.state.repo, app.state.workflow = repo, workflow
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])

    @app.middleware("http")
    async def local_browser_boundary(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and origin:
            parsed = urlparse(origin)
            if parsed.hostname not in {"127.0.0.1", "localhost", "testserver"} or parsed.scheme != request.url.scheme or parsed.port != request.url.port:
                return JSONResponse({"detail": "请从本机应用页面进行操作。"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; font-src 'self'; base-uri 'self'; frame-ancestors 'none'"
        return response

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/config")
    def config():
        return {"image_provider": settings.image_provider, "text_provider": settings.text_provider, "supports_edit": image_provider.supports_edit, "free_demo": settings.image_provider == "hf_space", "aspect_ratios": ["3:2", "1:1", "2:3"]}

    @app.post("/api/artworks", status_code=202)
    def create_artwork(value: ArtworkInput):
        artwork_id, job_id = repo.create_artwork(value)
        return {"artwork_id": artwork_id, "job_id": job_id}

    @app.get("/api/artworks")
    def history():
        return repo.list_artworks()

    @app.get("/api/artworks/{artwork_id}")
    def get_artwork(artwork_id: str):
        artwork = repo.get_artwork(artwork_id)
        if not artwork:
            raise HTTPException(404, "作品不存在。")
        return artwork

    @app.post("/api/artworks/{artwork_id}/revisions", status_code=202)
    def revise(artwork_id: str, value: RevisionInput):
        if not repo.get_artwork(artwork_id):
            raise HTTPException(404, "作品不存在。")
        if value.mode == "edit" and not image_provider.supports_edit:
            raise HTTPException(409, "当前模型不支持原图编辑，可选择按描述重新生成；构图可能改变。")
        try:
            job_id = repo.create_revision(artwork_id, value.source_version_id, value.instruction, value.mode)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        return {"artwork_id": artwork_id, "job_id": job_id}

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str):
        job = repo.get_job(job_id)
        if not job:
            raise HTTPException(404, "任务不存在。")
        return asdict(job)

    @app.get("/api/versions/{version_id}/image")
    def get_image(version_id: str, download: bool = False):
        version = repo.get_version(version_id)
        path = repo.image_path(version_id)
        if not version or not path or not path.is_file():
            raise HTTPException(404, "图片不存在。")
        return FileResponse(path, media_type=version["mime_type"], filename=version["filename"] if download else None)

    dist = ROOT / "frontend" / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    else:
        @app.get("/")
        def no_frontend():
            return JSONResponse({"detail": "请先在 frontend 目录运行 npm run build，或运行安装依赖脚本。"}, status_code=503)
    return app
