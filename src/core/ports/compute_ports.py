from abc import ABC, abstractmethod
from typing import Any, Dict, List


class IComputeDriverPort(ABC):
    """Port for executing compute tasks (local scripts, docker containers, remote jobs)."""

    @abstractmethod
    def run(self, command: List[str], inputs: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run a compute job and return a result dict with keys: returncode, stdout, stderr."""
        raise NotImplementedError

