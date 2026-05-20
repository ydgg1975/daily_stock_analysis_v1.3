"""Core orchestration package."""

from importlib import import_module


def __getattr__(name: str):
    """Lazily expose core modules for test patch paths."""
    try:
        module = import_module(f"{__name__}.{name}")
    except ModuleNotFoundError as exc:
        if exc.name == f"{__name__}.{name}":
            raise AttributeError(name) from exc
        raise
    globals()[name] = module
    return module
