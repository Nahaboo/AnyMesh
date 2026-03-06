"""
Async task queue with thread workers for mesh processing.
"""

import threading
import queue
import uuid
import random
from typing import Dict, Any, Callable
from datetime import datetime
from enum import Enum


class TaskStatus(Enum):
    """Possible task statuses."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Task:
    """A single processing task."""

    def __init__(self, task_id: str, task_type: str, params: Dict[str, Any]):
        self.id = task_id
        self.type = task_type
        self.params = params
        self.status = TaskStatus.PENDING
        self.progress = 0
        self.result = None
        self.error = None
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the task to a dict for the API."""
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status.value,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


class TaskManager:
    """Task queue with thread workers."""

    def __init__(self, num_workers: int = 2):
        self.task_queue = queue.Queue()
        self.tasks: Dict[str, Task] = {}
        self.task_handlers: Dict[str, Callable] = {}
        self.num_workers = num_workers
        self.workers = []
        self.running = False
        self.lock = threading.Lock()

        self.task_ttl_seconds = 3600  # Keep completed tasks for 1 hour
        self.max_tasks = 1000  # Max tasks in memory

    def register_handler(self, task_type: str, handler: Callable):
        """Register a handler function for a given task type."""
        self.task_handlers[task_type] = handler

    def create_task(self, task_type: str, params: Dict[str, Any]) -> str:
        """Create a task, enqueue it, and return its ID."""
        task_id = str(uuid.uuid4())
        task = Task(task_id, task_type, params)

        with self.lock:
            self.tasks[task_id] = task

        self.task_queue.put(task_id)
        return task_id

    def get_task(self, task_id: str) -> Task:
        """Return a task by ID."""
        with self.lock:
            return self.tasks.get(task_id)

    def get_all_tasks(self) -> Dict[str, Task]:
        """Return all tasks."""
        with self.lock:
            return dict(self.tasks)

    def cleanup_old_tasks(self):
        """Remove completed/failed tasks older than task_ttl_seconds. Called periodically by workers."""
        now = datetime.now()
        with self.lock:
            tasks_to_remove = []

            for task_id, task in self.tasks.items():
                if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                    if task.completed_at:
                        age = (now - task.completed_at).total_seconds()
                        if age > self.task_ttl_seconds:
                            tasks_to_remove.append(task_id)

            for task_id in tasks_to_remove:
                del self.tasks[task_id]

            if tasks_to_remove:
                print(f"[TASK_MANAGER] Cleaned up {len(tasks_to_remove)} old tasks (>{self.task_ttl_seconds}s)")

    def _worker(self, worker_id: int):
        """Thread worker. Processes tasks from the queue until stopped."""
        print(f"[WORKER-{worker_id}] Started and waiting for tasks...")
        while self.running:
            try:
                # 10% chance of cleanup per iteration to avoid memory leaks
                if random.random() < 0.1:
                    self.cleanup_old_tasks()

                task_id = self.task_queue.get(timeout=1)

                with self.lock:
                    task = self.tasks.get(task_id)

                if task is None:
                    continue

                task.status = TaskStatus.PROCESSING
                task.started_at = datetime.now()
                task.progress = 0

                print(f"[WORKER-{worker_id}] Processing task {task_id[:8]}... (type: {task.type})")

                try:
                    handler = self.task_handlers.get(task.type)
                    if handler is None:
                        raise ValueError(f"No handler for task type: {task.type}")

                    result = handler(task)

                    task.status = TaskStatus.COMPLETED
                    task.result = result
                    task.progress = 100
                    task.completed_at = datetime.now()

                    duration = (task.completed_at - task.started_at).total_seconds()
                    print(f"[WORKER-{worker_id}] Completed task {task_id[:8]} in {duration:.2f}s")

                except Exception as e:
                    task.status = TaskStatus.FAILED
                    task.error = str(e)
                    task.completed_at = datetime.now()
                    print(f"[WORKER-{worker_id}] Failed task {task_id[:8]}: {str(e)}")

                finally:
                    self.task_queue.task_done()

            except queue.Empty:
                continue
        print(f"[WORKER-{worker_id}] Stopped")

    def start(self):
        """Start the worker threads."""
        if self.running:
            return

        self.running = True
        print(f"[TASK_MANAGER] Starting {self.num_workers} worker threads...")
        for i in range(self.num_workers):
            worker = threading.Thread(target=self._worker, args=(i,), daemon=True)
            worker.start()
            self.workers.append(worker)

    def stop(self):
        """Stop the worker threads."""
        self.running = False
        for worker in self.workers:
            worker.join(timeout=5)
        self.workers = []

    def get_queue_size(self) -> int:
        """Return the number of pending tasks."""
        return self.task_queue.qsize()


# Global task manager instance
task_manager = TaskManager(num_workers=2)
