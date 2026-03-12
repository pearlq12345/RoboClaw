"""Dynamic driver loader — imports driver files from workspace at runtime."""

import importlib.util
import sys
from pathlib import Path
from typing import Any


class DriverLoader:
    """Load, reload, and manage driver instances from a workspace directory."""

    def __init__(self, drivers_dir: Path):
        self.drivers_dir = Path(drivers_dir)
        self.loaded: dict[str, Any] = {}  # name -> Driver instance
        self._modules: dict[str, Any] = {}  # name -> module

    def list_available(self) -> list[str]:
        """List driver names available on disk (*.py files in drivers_dir)."""
        if not self.drivers_dir.exists():
            return []
        return sorted(
            p.stem for p in self.drivers_dir.glob("*.py")
            if not p.name.startswith("_")
        )

    def load(self, name: str, reload: bool = False) -> Any:
        """Load a driver by name. Returns Driver instance.

        Args:
            name: Driver filename without .py extension.
            reload: If True, re-import even if already loaded.

        Raises:
            FileNotFoundError: Driver file doesn't exist.
            AttributeError: Driver file has no Driver class.
        """
        path = self.drivers_dir / f"{name}.py"
        if not path.exists():
            raise FileNotFoundError(f"Driver file not found: {path}")

        # Remove old module from sys.modules to force reload
        module_name = f"_nanobot_driver_{name}"
        if reload and module_name in sys.modules:
            del sys.modules[module_name]

        if not reload and name in self.loaded:
            return self.loaded[name]

        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create module spec for {path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        if not hasattr(module, "Driver"):
            raise AttributeError(f"Driver file {path} has no 'Driver' class")

        instance = module.Driver()
        self.loaded[name] = instance
        self._modules[name] = module
        return instance

    def unload(self, name: str) -> None:
        """Remove a loaded driver."""
        self.loaded.pop(name, None)
        module_name = f"_nanobot_driver_{name}"
        sys.modules.pop(module_name, None)
        self._modules.pop(name, None)

    def get_driver_info(self, name: str) -> dict:
        """Get info about a loaded driver."""
        driver = self.loaded.get(name)
        if not driver:
            return {"error": f"Driver '{name}' not loaded"}
        return {
            "name": driver.name,
            "description": getattr(driver, "description", ""),
            "methods": driver.methods,
        }
