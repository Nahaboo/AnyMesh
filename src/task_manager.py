"""
Gestionnaire de taches asynchrones pour le traitement de maillages
"""

import threading
import queue
import uuid
from typing import Dict, Any, Callable
from datetime import datetime
from enum import Enum


class TaskStatus(Enum):
    """Statuts possibles d'une tache"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Task:
    """Representation d'une tache de traitement"""

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
        """Convertit la tache en dictionnaire pour l'API"""
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
    """
    Gestionnaire de file d'attente de taches avec workers threads
    """

    def __init__(self, num_workers: int = 2):
        """
        Args:
            num_workers: Nombre de threads workers pour traiter les taches
        """
        self.task_queue = queue.Queue()
        self.tasks: Dict[str, Task] = {}
        self.task_handlers: Dict[str, Callable] = {}
        self.num_workers = num_workers
        self.workers = []
        self.running = False
        self.lock = threading.Lock()

    def register_handler(self, task_type: str, handler: Callable):
        """
        Enregistre une fonction pour traiter un type de tache specifique

        Args:
            task_type: Type de tache (ex: "simplify")
            handler: Fonction qui prend une Task et retourne le resultat
        """
        self.task_handlers[task_type] = handler

    def create_task(self, task_type: str, params: Dict[str, Any]) -> str:
        """
        Cree une nouvelle tache et l'ajoute a la file d'attente

        Args:
            task_type: Type de tache
            params: Parametres de la tache

        Returns:
            ID de la tache creee
        """
        task_id = str(uuid.uuid4())
        task = Task(task_id, task_type, params)

        with self.lock:
            self.tasks[task_id] = task

        self.task_queue.put(task_id)
        return task_id

    def get_task(self, task_id: str) -> Task:
        """Recupere une tache par son ID"""
        with self.lock:
            return self.tasks.get(task_id)

    def get_all_tasks(self) -> Dict[str, Task]:
        """Recupere toutes les taches"""
        with self.lock:
            return dict(self.tasks)

    def _worker(self, worker_id: int):
        """Thread worker qui traite les taches de la file d'attente"""
        print(f"[WORKER-{worker_id}] Started and waiting for tasks...")
        while self.running:
            try:
                # Recupere une tache avec timeout pour permettre l'arret propre
                task_id = self.task_queue.get(timeout=1)

                with self.lock:
                    task = self.tasks.get(task_id)

                if task is None:
                    continue

                # Marque la tache comme en cours
                task.status = TaskStatus.PROCESSING
                task.started_at = datetime.now()
                task.progress = 0

                print(f"[WORKER-{worker_id}] Processing task {task_id[:8]}... (type: {task.type})")

                try:
                    # Execute le handler correspondant au type de tache
                    handler = self.task_handlers.get(task.type)
                    if handler is None:
                        raise ValueError(f"Aucun handler pour le type de tache: {task.type}")

                    # Execute la tache
                    result = handler(task)

                    # Marque la tache comme completee
                    task.status = TaskStatus.COMPLETED
                    task.result = result
                    task.progress = 100
                    task.completed_at = datetime.now()

                    duration = (task.completed_at - task.started_at).total_seconds()
                    print(f"[WORKER-{worker_id}] Completed task {task_id[:8]} in {duration:.2f}s")

                except Exception as e:
                    # Marque la tache comme echouee
                    task.status = TaskStatus.FAILED
                    task.error = str(e)
                    task.completed_at = datetime.now()
                    print(f"[WORKER-{worker_id}] Failed task {task_id[:8]}: {str(e)}")

                finally:
                    self.task_queue.task_done()

            except queue.Empty:
                # Pas de tache disponible, continue d'attendre
                continue
        print(f"[WORKER-{worker_id}] Stopped")

    def start(self):
        """Demarre les threads workers"""
        if self.running:
            return

        self.running = True
        print(f"[TASK_MANAGER] Starting {self.num_workers} worker threads...")
        for i in range(self.num_workers):
            worker = threading.Thread(target=self._worker, args=(i,), daemon=True)
            worker.start()
            self.workers.append(worker)

    def stop(self):
        """Arrete les threads workers"""
        self.running = False
        for worker in self.workers:
            worker.join(timeout=5)
        self.workers = []

    def get_queue_size(self) -> int:
        """Retourne le nombre de taches en attente"""
        return self.task_queue.qsize()


# Instance globale du gestionnaire de taches
task_manager = TaskManager(num_workers=2)
