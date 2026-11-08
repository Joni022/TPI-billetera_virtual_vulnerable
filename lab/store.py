import json
import re
import shutil
import threading
from pathlib import Path


class RunStore:
    """Registro acotado; los datos de la billetera nunca se guardan aquí."""

    def __init__(self, directory):
        self.root = Path(directory).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def directory(self, run_id):
        if not re.fullmatch(r"[a-f0-9]{32}", run_id):
            raise ValueError("Identificador inválido")
        path = (self.root / run_id).resolve()
        if path.parent != self.root:
            raise ValueError("Directorio inválido")
        return path

    def save(self, run):
        with self.lock:
            path = self.directory(run["id"])
            path.mkdir(exist_ok=True)
            temporary = path / "result.tmp"
            temporary.write_text(json.dumps(run, ensure_ascii=False), encoding="utf-8")
            temporary.replace(path / "result.json")

    def get(self, run_id):
        with self.lock:
            try:
                return json.loads((self.directory(run_id) / "result.json").read_text(encoding="utf-8"))
            except (FileNotFoundError, ValueError, json.JSONDecodeError):
                return None

    def recent(self):
        with self.lock:
            runs = [self.get(path.name) for path in self.root.iterdir()
                    if path.is_dir() and re.fullmatch(r"[a-f0-9]{32}", path.name)]
            return sorted((run for run in runs if run), key=lambda run: run["created_at"], reverse=True)[:10]

    def prune(self):
        with self.lock:
            keep = {run["id"] for run in self.recent()}
            for path in self.root.iterdir():
                if path.is_dir() and re.fullmatch(r"[a-f0-9]{32}", path.name) and path.name not in keep:
                    checked = self.directory(path.name)
                    if checked.parent == self.root and not path.is_symlink():
                        shutil.rmtree(checked)
