import subprocess
from typing import Any, Dict, List

from ...core.ports.compute_ports import IComputeDriverPort


class LocalComputeDriver(IComputeDriverPort):
	NAME = "local"

	def run(self, command: List[str], inputs: Dict[str, Any] = None) -> Dict[str, Any]:
		proc = subprocess.Popen(
			command,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			text=True,
		)
		out, err = proc.communicate()
		return {"returncode": proc.returncode, "stdout": out, "stderr": err}


