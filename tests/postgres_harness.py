import shutil
import socket
import subprocess
import tempfile
from pathlib import Path


class TemporaryPostgres:
    def __init__(self):
        self._initdb = shutil.which("initdb")
        self._pg_ctl = shutil.which("pg_ctl")
        self._postgres = shutil.which("postgres")
        if not all((self._initdb, self._pg_ctl, self._postgres)):
            raise RuntimeError("PostgreSQL binaries not found in PATH")

        self.root_dir = Path(tempfile.mkdtemp(prefix="tourist03-pgtest-"))
        self.data_dir = self.root_dir / "data"
        self.log_file = self.root_dir / "postgres.log"
        self.port = self._allocate_port()
        self.started = False

    @staticmethod
    def _allocate_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    def _run(self, *args: str) -> None:
        result = subprocess.run(
            list(args),
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return

        details = []
        if result.stdout.strip():
            details.append(f"stdout:\n{result.stdout.strip()}")
        if result.stderr.strip():
            details.append(f"stderr:\n{result.stderr.strip()}")
        rendered = "\n".join(details) if details else "no output"
        raise RuntimeError(f"Command failed: {' '.join(args)}\n{rendered}")

    def start(self) -> None:
        self._run(
            self._initdb,
            "-D",
            str(self.data_dir),
            "-A",
            "trust",
            "-U",
            "postgres",
            "--no-instructions",
        )
        self._run(
            self._pg_ctl,
            "-D",
            str(self.data_dir),
            "-l",
            str(self.log_file),
            "-o",
            f"-F -p {self.port}",
            "-w",
            "start",
        )
        self.started = True

    def stop(self) -> None:
        try:
            if self.started:
                self._run(
                    self._pg_ctl,
                    "-D",
                    str(self.data_dir),
                    "-m",
                    "immediate",
                    "stop",
                )
        finally:
            shutil.rmtree(self.root_dir, ignore_errors=True)
            self.started = False

    def as_environ(self) -> dict[str, str]:
        return {
            "PG_HOST": "127.0.0.1",
            "PG_PORT": str(self.port),
            "PG_DB": "postgres",
            "PG_USER": "postgres",
            "PG_PASSWORD": "",
        }
