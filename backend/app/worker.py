import asyncio
import uuid


class Worker:
    def __init__(self, repository, workflow):
        self.repo, self.workflow = repository, workflow
        self.owner = uuid.uuid4().hex
        self.task = self.heartbeat = None

    async def start(self):
        if not self.repo.acquire_lease(self.owner):
            raise RuntimeError("已有应用实例在处理任务，请关闭重复窗口后再启动。")
        self.repo.recover_running()
        self.task = asyncio.create_task(self.loop())
        self.heartbeat = asyncio.create_task(self.renew())

    async def loop(self):
        while True:
            job = self.repo.claim()
            if job:
                await self.workflow.run(job)
            else:
                await asyncio.sleep(0.6)

    async def renew(self):
        while True:
            await asyncio.sleep(5)
            if not self.repo.acquire_lease(self.owner):
                self.task.cancel()
                raise RuntimeError("任务处理租约已丢失，已停止生成。")

    async def stop(self):
        for task in (self.task, self.heartbeat):
            if task:
                task.cancel()
        for task in (self.task, self.heartbeat):
            if task:
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self.repo.release_lease(self.owner)
