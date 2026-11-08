import os
import threading

import requests
from flask import Flask, Response, request
from werkzeug.serving import make_server

from lab.app import create_app


def proxy_app(upstream, port):
    app = Flask("wallet_proxy_" + str(port))
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024

    @app.route("/", defaults={"path": ""}, methods=["GET", "POST"])
    @app.route("/<path:path>", methods=["GET", "POST"])
    def proxy(path):
        # Upstream is deployment configuration, never a request argument.
        headers = {key: value for key, value in request.headers if key.lower() in
                   {"cookie", "content-type", "origin", "x-csrf-token", "referer", "accept"}}
        headers["Host"] = f"localhost:{port}"
        try:
            # No shared cookie jar: browser contexts must remain independent.
            with requests.Session() as client:
                client.trust_env = False
                result = client.request(request.method, upstream + "/" + path,
                                        params=request.args, headers=headers, data=request.get_data(),
                                        allow_redirects=False, timeout=(3, 20))
            response = Response(result.content, result.status_code)
            for key in ("Content-Type", "Content-Security-Policy", "Cache-Control", "Retry-After", "Location"):
                if key in result.headers:
                    response.headers[key] = result.headers[key]
            for cookie in result.raw.headers.getlist("Set-Cookie"):
                response.headers.add("Set-Cookie", cookie)
            return response
        except requests.RequestException:
            return {"error": "Billetera no disponible"}, 503

    return app


def attacker_app():
    app = Flask("csrf_demonstration")

    @app.get("/")
    def attacker():
        variant = request.args.get("variant")
        if variant is None:
            return '''<!doctype html><html lang="es"><meta charset="utf-8"><title>Demostración CSRF · Umbral</title>
            <body><h1>Página atacante de demostración</h1><p>Iniciá sesión como ana en la billetera antes de elegir.</p>
            <p>La opción envía una transferencia ficticia de $25 a bruno, utilizando la sesión abierta.</p>
            <p><a href="/?variant=vulnerable">Probar billetera vulnerable</a></p>
            <p><a href="/?variant=secure">Probar billetera corregida</a></p></body></html>'''
        if variant not in ("vulnerable", "secure"):
            return "Versión desconocida", 400
        port = 5000 if variant == "vulnerable" else 5001
        # Fixed, harmless local demonstration. No destination or payload from user input.
        return f'''<!doctype html><html lang="es"><meta charset="utf-8"><title>Demostración CSRF · Umbral</title>
        <body><h1>Página atacante de demostración</h1><p>Se enviará una transferencia ficticia de $25 a bruno.</p>
        <form id="csrf-form" data-testid="csrf-form" action="http://localhost:{port}/api/transfers" method="post">
        <input type="hidden" name="recipient" value="bruno"><input type="hidden" name="amount_cents" value="2500">
        <input type="hidden" name="concept" value="Demostración CSRF"><button>Enviar demostración</button></form>
        <script>document.getElementById('csrf-form').submit()</script></body></html>'''

    return app


def serve_background(app, host, port):
    server = make_server(host, port, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main():
    servers = []
    if os.environ.get("LAB_PROXIES", "1") == "1":
        servers.append(serve_background(proxy_app(os.environ.get("VULNERABLE_UPSTREAM", "http://vulnerable:5000"), 5000), "127.0.0.1", 5000))
        servers.append(serve_background(proxy_app(os.environ.get("SECURE_UPSTREAM", "http://secure:5001"), 5001), "127.0.0.1", 5001))
    servers.append(serve_background(attacker_app(), "0.0.0.0" if os.environ.get("IN_DOCKER") == "1" else "127.0.0.1", 5003))
    app = create_app()
    server = make_server("0.0.0.0" if os.environ.get("IN_DOCKER") == "1" else "127.0.0.1", 5002, app, threaded=True)
    try:
        server.serve_forever()
    finally:
        if app.manager.active_id:
            app.manager.cancel(app.manager.active_id)
        for running in servers:
            running.shutdown()


if __name__ == "__main__":
    main()
