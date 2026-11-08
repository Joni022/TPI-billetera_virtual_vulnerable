import os
import secrets
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory
from flask_wtf.csrf import CSRFError, CSRFProtect, generate_csrf

from lab.runner import BusyError, LabManager, ResetRequired

ROOT = Path(__file__).resolve().parent.parent


def read_control_token():
    path = Path(os.environ.get("LAB_CONTROL_TOKEN_FILE", "/secrets/control-token"))
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise RuntimeError("Canal de control no preparado") from error


def create_app(manager=None):
    app = Flask(__name__, static_folder=None)
    app.config.update(SECRET_KEY=secrets.token_hex(32), SESSION_COOKIE_NAME="umbral_guide",
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict",
                      MAX_CONTENT_LENGTH=4096, WTF_CSRF_TIME_LIMIT=7200)
    CSRFProtect(app)
    if manager is None:
        controls = {"vulnerable": os.environ.get("VULNERABLE_CONTROL", "http://vulnerable:9001"),
                    "secure": os.environ.get("SECURE_CONTROL", "http://secure:9001")}
        manager = LabManager(os.environ.get("LAB_DATA_DIR", str(ROOT / ".runtime" / "guide")), controls, read_control_token)
    app.manager = manager
    dist = Path(os.environ.get("FRONTEND_DIR", ROOT / "frontend" / "dist"))

    @app.before_request
    def origin_guard():
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if request.headers.get("Origin") not in ("http://localhost:5002", "http://127.0.0.1:5002"):
                return jsonify(error="Origen no permitido"), 403
            if not request.is_json:
                return jsonify(error="Se requiere JSON"), 415

    @app.after_request
    def headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @app.errorhandler(CSRFError)
    def csrf_error(_error):
        return jsonify(error="Token CSRF inválido o ausente. Recargar la guía."), 400

    @app.get("/lab/api/csrf-token")
    def csrf_token():
        return jsonify(token=generate_csrf())

    @app.get("/lab/api/status")
    def status():
        return jsonify(active=manager.lock.locked(), needs_reset=manager.needs_reset,
                       active_run_id=manager.active_id,
                       variants={"vulnerable": {"url": "http://localhost:5000"}, "secure": {"url": "http://localhost:5001"}},
                       credentials=[{"username": name, "password": "Demo1234!", "role": "admin" if name == "admin" else "user"}
                                    for name in ("ana", "bruno", "admin")],
                       reset_results=manager.reset_results)

    @app.post("/lab/api/reset")
    def reset():
        if request.get_json(silent=True) != {}:
            return jsonify(error="El reinicio no admite parámetros"), 400
        try:
            value = manager.reset()
            return jsonify(value), 200 if value["status"] == "complete" else 503
        except BusyError:
            return jsonify(error="Hay una operación en curso"), 409

    @app.get("/lab/api/runs")
    def runs():
        return jsonify(runs=manager.store.recent())

    @app.post("/lab/api/runs")
    def start():
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or set(body) - {"case_id", "reset_first"} or not isinstance(body.get("reset_first", False), bool):
            return jsonify(error="Parámetros inválidos"), 400
        try:
            value = manager.start(body.get("case_id"), body.get("reset_first", False))
            return jsonify(value), 202
        except ValueError:
            return jsonify(error="Ejercicio desconocido"), 400
        except BusyError:
            return jsonify(error="Hay una operación en curso"), 409
        except ResetRequired:
            return jsonify(error="Restablecer ambas billeteras antes del próximo ejercicio"), 409

    @app.get("/lab/api/runs/<run_id>")
    def run(run_id):
        value = manager.store.get(run_id)
        if value is None:
            abort(404)
        return jsonify(value)

    @app.post("/lab/api/runs/<run_id>/cancel")
    def cancel(run_id):
        if not manager.cancel(run_id):
            return jsonify(error="La ejecución no está activa"), 409
        return jsonify(ok=True), 202

    @app.get("/lab/artifacts/<run_id>/<path:filename>")
    def artifact(run_id, filename):
        if manager.store.get(run_id) is None or not filename.endswith(".png"):
            abort(404)
        return send_from_directory(manager.store.directory(run_id), filename)

    @app.get("/health")
    def health():
        return jsonify(ok=True)

    @app.get("/")
    @app.get("/<path:filename>")
    def frontend(filename="guide.html"):
        if filename.startswith(("api/", "lab/")):
            abort(404)
        if (dist / filename).is_file():
            return send_from_directory(dist, filename)
        return send_from_directory(dist, "guide.html")

    return app
