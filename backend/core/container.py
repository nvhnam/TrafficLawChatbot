import threading
from typing import Callable, TypeVar

T = TypeVar("T")


class ServiceContainer:
    """Lazy singleton service locator. Services are instantiated on first access."""

    _instances: dict = {}
    # RLock (not Lock): a service factory may itself call ServiceContainer.get()
    # for another service (e.g. GraphRAG_Bot's factory fetching the shared
    # embedding-model singleton) from the same thread while this lock is held.
    _lock = threading.RLock()

    @classmethod
    def get(cls, name: str, factory: Callable[[], T]) -> T:
        if name not in cls._instances:
            with cls._lock:
                if name not in cls._instances:
                    cls._instances[name] = factory()
        return cls._instances[name]

    @classmethod
    def reset(cls, name: str | None = None) -> None:
        with cls._lock:
            if name:
                cls._instances.pop(name, None)
            else:
                cls._instances.clear()
