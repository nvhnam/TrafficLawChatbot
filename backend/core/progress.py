import threading
from dataclasses import dataclass, field


@dataclass
class ProgressState:
    is_running: bool = False
    phase: str = "idle"
    total_files: int = 0
    processed_files: int = 0
    current_file: str = ""
    message: str = "He thong dang ranh roi"


class ProgressTracker:
    """Thread-safe progress tracker replacing the global progress_status dict."""

    def __init__(self):
        self._state = ProgressState()
        self._lock = threading.Lock()

    def update(self, **kwargs) -> None:
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self._state, k):
                    setattr(self._state, k, v)

    def increment_processed(self) -> None:
        with self._lock:
            self._state.processed_files += 1

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "is_running": self._state.is_running,
                "phase": self._state.phase,
                "total_files": self._state.total_files,
                "processed_files": self._state.processed_files,
                "current_file": self._state.current_file,
                "message": self._state.message,
            }

    def reset(self) -> None:
        with self._lock:
            self._state = ProgressState()
