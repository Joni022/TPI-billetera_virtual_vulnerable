import json
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests

from lab.store import RunStore

CASES = ("access-control", "csrf", "xss", "sqli", "authentication", "ssrf")
VARIANTS = ("vulnerable", "secure")
ROOT = Path(__file__).resolve().parent.parent
CASE_TIMEOUT_SECONDS = 90


class BusyError(Exception):
    pass


class ResetRequired(Exception):
    pass


class LabManager:
    def __init__(self, directory, controls, token_loader, bases=None):
        self.store = RunStore(Path(directory) / "runs")
        self.controls = controls
        self.token_loader = token_loader
        self.bases = bases or {"vulnerable": "http://localhost:5000", "secure": "http://localhost:5001"}
        self.lock = threading.Lock()
        self.active_id = None
        self.cancel_event = threading.Event()
        self.needs_reset = True
        self.reset_results = {}
        self.client = requests.Session()
        self.client.trust_env = False
        for run in self.store.recent():
            if run["status"] in ("queued", "running"):
                run.update(status="error", error="El ejecutor se reinició; resultado inconcluso.")
                self.store.save(run)

    def control(self, variant, path, operation_id=None):
        token = self.token_loader()
        if not token:
            raise RuntimeError("Canal de control no preparado")
        method = self.client.post if operation_id else self.client.get
        arguments = {"headers": {"Authorization": "Bearer " + token}, "timeout": (3, 20), "allow_redirects": False}
        if operation_id:
            arguments["json"] = {"operation_id": operation_id}
        response = method(self.controls[variant] + path, **arguments)
        response.raise_for_status()
        return response.json()

    def _reset(self):
        results = {}
        for variant in VARIANTS:
            operation_id = uuid.uuid4().hex
            try:
                value = self.control(variant, "/internal/reset", operation_id)
                results[variant] = {"ok": value.get("ok") is True, "generation": value.get("generation")}
            except (requests.RequestException, RuntimeError, ValueError):
                # A lost response is not proof that the transaction rolled back.
                try:
                    state = self.control(variant, "/internal/status")
                    confirmed = state.get("operation_id") == operation_id
                    results[variant] = {"ok": confirmed, "generation": state.get("generation"),
                                        "error": None if confirmed else "No se pudo confirmar el reinicio; volver a restablecer."}
                except (requests.RequestException, RuntimeError, ValueError):
                    results[variant] = {"ok": False, "error": "No se pudo confirmar el reinicio; volver a restablecer."}
        self.reset_results = results
        complete = all(value["ok"] for value in results.values())
        self.needs_reset = not complete
        return {"status": "complete" if complete else "partial" if any(v["ok"] for v in results.values()) else "failed",
                "variants": results}

    def reset(self):
        if not self.lock.acquire(blocking=False):
            raise BusyError()
        try:
            return self._reset()
        finally:
            self.lock.release()

    def start(self, case_id, reset_first=False):
        if case_id not in (*CASES, "all"):
            raise ValueError("Ejercicio desconocido")
        if not self.lock.acquire(blocking=False):
            raise BusyError()
        if self.needs_reset and not reset_first and case_id != "all":
            self.lock.release()
            raise ResetRequired()
        run = {"id": uuid.uuid4().hex, "case_id": case_id, "status": "queued", "results": [], "error": None,
               "created_at": datetime.now(timezone.utc).isoformat(), "finished_at": None}
        self.active_id = run["id"]
        self.cancel_event = threading.Event()
        self.store.save(run)
        self.store.prune()
        thread = threading.Thread(target=self._run, args=(run, reset_first), daemon=True)
        thread.start()
        return run

    def cancel(self, run_id):
        if self.active_id == run_id:
            self.cancel_event.set()
            return True
        return False

    def _case_process(self, run, case_id, variant):
        output = self.store.directory(run["id"]) / f"{case_id}-{variant}"
        output.mkdir(exist_ok=True)
        command = [sys.executable, "-m", "lab.worker", case_id, variant, self.bases[variant], str(output)]
        # Fixed module and case IDs only; no shell and no executable supplied by the browser.
        environment = dict(os.environ, PYTHONUNBUFFERED="1")
        process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, start_new_session=os.name != 'nt')
        deadline = time.monotonic() + CASE_TIMEOUT_SECONDS
        interrupted = None
        try:
            while process.poll() is None:
                if self.cancel_event.is_set():
                    interrupted = "Ejecución cancelada"
                    break
                if time.monotonic() > deadline:
                    interrupted = "Tiempo máximo del ejercicio agotado"
                    break
                time.sleep(0.15)
        finally:
            if process.poll() is None:
                if os.name != 'nt':
                    os.killpg(process.pid, signal.SIGTERM)
                else:
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                try:
                    process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    if os.name != 'nt':
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                    process.wait(timeout=4)
                if os.name != 'nt':
                    # The Python worker may exit before a browser descendant.
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
        if interrupted:
            return {"outcome": "inconclusive", "evidence": {"summary": interrupted}}
        try:
            result = json.loads((output / "worker-result.json").read_text(encoding="utf-8"))
            if result.get("outcome") not in ("attack_reproduced", "blocked", "unexpected", "inconclusive"):
                raise ValueError()
            evidence = result.setdefault("evidence", {})
            screenshots = []
            for path in sorted(output.glob("*.png"), key=lambda path: (0 if path.name == "before.png" else 1, path.name)):
                if path.is_file() and not path.is_symlink():
                    screenshots.append(f"/lab/artifacts/{run['id']}/{output.name}/{path.name}")
            evidence["screenshots"] = screenshots
            return result
        except (OSError, ValueError, TypeError):
            return {"outcome": "inconclusive", "evidence": {"summary": "El ejecutor no produjo evidencia válida."}}

    def _run(self, run, reset_first):
        try:
            run["status"] = "running"
            self.store.save(run)
            for case_id in CASES if run["case_id"] == "all" else (run["case_id"],):
                if self.cancel_event.is_set():
                    break
                if run["case_id"] == "all" or reset_first:
                    reset = self._reset()
                    if reset["status"] != "complete":
                        raise RuntimeError("Reinicio incompleto: comprobar ambas versiones antes de continuar.")
                for variant in VARIANTS:
                    if self.cancel_event.is_set():
                        break
                    run["current"] = {"case_id": case_id, "variant": variant}
                    self.store.save(run)
                    result = self._case_process(run, case_id, variant)
                    result.update(case_id=case_id, variant=variant)
                    run["results"].append(result)
                    self.store.save(run)
            run["status"] = "cancelled" if self.cancel_event.is_set() else "completed"
        except Exception:
            run.update(status="error", error="No se completó la ejecución. Restablecer ambas billeteras y comprobar los servicios.")
        finally:
            # Leave actual wallet effects in place for the presentation.
            self.needs_reset = True
            run["current"] = None
            run["finished_at"] = datetime.now(timezone.utc).isoformat()
            self.store.save(run)
            self.active_id = None
            self.lock.release()
