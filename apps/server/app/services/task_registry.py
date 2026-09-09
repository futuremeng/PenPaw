"""进程内任务注册表（M1：Stage 3 进程内异步 + SSE 进度）。

M3 接入真实 DiffVG 后，跨进程状态迁移到 Celery + Redis
（见 app/tasks/ 说明），本模块的 SSE 轮询接口保持不变。
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field


@dataclass
class TaskState:
    task_id: str
    asset_id: str
    status: str = "queued"  # queued | running | succeeded | degraded | failed
    progress: float = 0.0
    error: str | None = None
    control_points: int | None = None
    created_at: float = field(default_factory=time.time)

    @property
    def is_terminal(self) -> bool:
        return self.status in ("succeeded", "degraded", "failed")


class TaskRegistry:
    def __init__(self) -> None:
        self._tasks: dict[str, TaskState] = {}
        self._lock = threading.Lock()

    def create(self, asset_id: str) -> TaskState:
        task = TaskState(task_id=uuid.uuid4().hex, asset_id=asset_id)
        with self._lock:
            self._tasks[task.task_id] = task
        return task

    def get(self, task_id: str) -> TaskState | None:
        with self._lock:
            return self._tasks.get(task_id)

    def update(
        self,
        task_id: str,
        status: str | None = None,
        progress: float | None = None,
        error: str | None = None,
        control_points: int | None = None,
    ) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            if status is not None:
                task.status = status
            if progress is not None:
                task.progress = progress
            if error is not None:
                task.error = error
            if control_points is not None:
                task.control_points = control_points

    def run_async(self, task_id: str, fn) -> None:
        """在后台线程执行 fn(progress_cb)，异常时标记 failed。"""
        def _worker() -> None:
            self.update(task_id, status="running")
            try:
                result = fn(self._make_progress_cb(task_id))
                self.update(
                    task_id,
                    status=result.get("status", "succeeded"),
                    progress=1.0,
                    control_points=result.get("control_points"),
                    error=result.get("error"),
                )
            except Exception as exc:  # noqa: BLE001 - 顶层兜底，降级由调用方语义决定
                self.update(task_id, status="failed", error=str(exc))

        threading.Thread(target=_worker, daemon=True).start()

    def _make_progress_cb(self, task_id: str):
        def cb(progress: float) -> None:
            self.update(task_id, progress=progress)

        return cb
