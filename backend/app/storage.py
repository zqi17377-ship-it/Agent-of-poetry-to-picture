import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from .models import ArtworkInput, JobRecord
from .providers.http_utils import verify_image


def timestamp():
    return datetime.now(timezone.utc).isoformat()


class Repository:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.images_dir = self.data_dir / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "studio.sqlite3"
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS artworks (id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS versions (id TEXT PRIMARY KEY, artwork_id TEXT NOT NULL REFERENCES artworks(id), payload TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, artwork_id TEXT NOT NULL REFERENCES artworks(id), status TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status, created_at);
                CREATE TABLE IF NOT EXISTS worker_lease (id INTEGER PRIMARY KEY CHECK(id=1), owner TEXT NOT NULL, expires REAL NOT NULL);
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.db_path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def _insert_job(self, db, artwork_id, operation, source_version_id=None, instruction=""):
        job = JobRecord(uuid.uuid4().hex, artwork_id, "queued", operation, source_version_id, instruction)
        db.execute("INSERT INTO jobs VALUES(?,?,?,?,?)", (job.id, artwork_id, job.status, json.dumps(asdict(job), ensure_ascii=False), timestamp()))
        return job.id

    def create_artwork(self, value: ArtworkInput):
        artwork_id = uuid.uuid4().hex
        payload = value.model_dump()
        payload["title"] = value.title.strip() or value.text.splitlines()[0][:30]
        with self.connection() as db:
            db.execute("INSERT INTO artworks VALUES(?,?,?)", (artwork_id, json.dumps(payload, ensure_ascii=False), timestamp()))
            job_id = self._insert_job(db, artwork_id, "generate")
        return artwork_id, job_id

    def get_artwork(self, artwork_id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM artworks WHERE id=?", (artwork_id,)).fetchone()
            if row is None:
                return None
            versions = [json.loads(item[0]) for item in db.execute("SELECT payload FROM versions WHERE artwork_id=? ORDER BY created_at", (artwork_id,))]
            jobs = [json.loads(item[0]) for item in db.execute("SELECT payload FROM jobs WHERE artwork_id=? ORDER BY created_at", (artwork_id,))]
        return {"id": artwork_id, **json.loads(row["payload"]), "created_at": row["created_at"], "versions": versions, "jobs": jobs}

    def list_artworks(self):
        with self.connection() as db:
            rows = db.execute("SELECT id, payload, created_at FROM artworks ORDER BY created_at DESC LIMIT 100").fetchall()
            results = []
            for row in rows:
                payload = json.loads(row["payload"])
                last = db.execute("SELECT payload FROM versions WHERE artwork_id=? ORDER BY created_at DESC LIMIT 1", (row["id"],)).fetchone()
                job = db.execute("SELECT status FROM jobs WHERE artwork_id=? ORDER BY created_at DESC LIMIT 1", (row["id"],)).fetchone()
                results.append({"id": row["id"], "title": payload["title"], "author": payload["author"], "created_at": row["created_at"], "latest_version": json.loads(last[0]) if last else None, "status": job[0] if job else "failed"})
            return results

    def get_version(self, version_id):
        with self.connection() as db:
            row = db.execute("SELECT payload FROM versions WHERE id=?", (version_id,)).fetchone()
            return json.loads(row[0]) if row else None

    def image_path(self, version_id):
        version = self.get_version(version_id)
        return self.images_dir / version["filename"] if version else None

    def create_revision(self, artwork_id, source_version_id, instruction, mode):
        with self.connection() as db:
            row = db.execute("SELECT artwork_id FROM versions WHERE id=?", (source_version_id,)).fetchone()
            if row is None or row[0] != artwork_id:
                raise ValueError("请选择这幅作品的已有版本。")
            return self._insert_job(db, artwork_id, mode, source_version_id, instruction)

    def get_job(self, job_id):
        with self.connection() as db:
            row = db.execute("SELECT payload FROM jobs WHERE id=?", (job_id,)).fetchone()
            return JobRecord(**json.loads(row[0])) if row else None

    def update_job(self, job_id, **changes):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise ValueError("任务不存在。")
            payload = json.loads(row[0])
            payload.update(changes)
            db.execute("UPDATE jobs SET status=?, payload=? WHERE id=?", (payload["status"], json.dumps(payload, ensure_ascii=False), job_id))

    def claim(self):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM jobs WHERE status='running' LIMIT 1").fetchone():
                return None
            row = db.execute("SELECT payload FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            if not row:
                return None
            payload = json.loads(row[0]); payload["status"] = "running"
            db.execute("UPDATE jobs SET status='running', payload=? WHERE id=?", (json.dumps(payload, ensure_ascii=False), payload["id"]))
            return JobRecord(**payload)

    def recover_running(self):
        with self.connection() as db:
            for row in db.execute("SELECT id,payload FROM jobs WHERE status='running'").fetchall():
                payload = json.loads(row["payload"])
                payload.update(status="needs_review", error="上次运行中断，已停止自动重试。请核查生成服务后再重新生成。")
                db.execute("UPDATE jobs SET status='needs_review', payload=? WHERE id=?", (json.dumps(payload, ensure_ascii=False), row["id"]))

    def save_version(self, job, data, metadata):
        mime = verify_image(data)
        extension = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}[mime]
        version_id = uuid.uuid4().hex
        filename = version_id + extension
        path = self.images_dir / filename
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(data)
        temporary.replace(path)
        payload = {"id": version_id, "artwork_id": job.artwork_id, "parent_version_id": job.source_version_id, "revision_text": job.instruction, "operation": job.operation, "filename": filename, "mime_type": mime, "created_at": timestamp(), **metadata}
        with self.connection() as db:
            db.execute("INSERT INTO versions VALUES(?,?,?,?)", (version_id, job.artwork_id, json.dumps(payload, ensure_ascii=False), payload["created_at"]))
            current = json.loads(db.execute("SELECT payload FROM jobs WHERE id=?", (job.id,)).fetchone()[0])
            current.update(status="succeeded", stage="done", error=None)
            db.execute("UPDATE jobs SET status='succeeded', payload=? WHERE id=?", (json.dumps(current, ensure_ascii=False), job.id))
        return payload

    def acquire_lease(self, owner):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT owner,expires FROM worker_lease WHERE id=1").fetchone()
            if row and row["owner"] != owner and row["expires"] > time.time():
                return False
            db.execute("INSERT OR REPLACE INTO worker_lease VALUES(1,?,?)", (owner, time.time() + 30))
            return True

    def release_lease(self, owner):
        with self.connection() as db:
            db.execute("DELETE FROM worker_lease WHERE owner=?", (owner,))
