"""Fixed reverse proxies between local published ports and the isolated lab."""
import threading

import requests
from flask import Flask, Response, request
from werkzeug.serving import make_server

DESTINATIONS = {
    5000: 'http://vulnerable:5000',
    5001: 'http://secure:5001',
    5002: 'http://lab:5002',
    5003: 'http://lab:5003',
}


def create_proxy(port):
    upstream = DESTINATIONS[port]
    app = Flask(f'gateway_{port}')
    app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024

    @app.route('/', defaults={'path': ''}, methods=['GET', 'POST'])
    @app.route('/<path:path>', methods=['GET', 'POST'])
    def proxy(path):
        allowed = {'cookie', 'content-type', 'origin', 'x-csrf-token', 'referer', 'accept'}
        headers = {key: value for key, value in request.headers if key.lower() in allowed}
        headers['Host'] = f'localhost:{port}'
        try:
            # A fresh client prevents one visitor's cookies leaking into another request.
            with requests.Session() as client:
                client.trust_env = False
                result = client.request(request.method, upstream + '/' + path,
                                        params=request.args, headers=headers,
                                        data=request.get_data(), allow_redirects=False,
                                        timeout=(3, 30))
            response = Response(result.content, status=result.status_code)
            for key in ('Content-Type', 'Content-Security-Policy', 'Cache-Control',
                        'Retry-After', 'Location', 'X-Content-Type-Options'):
                if key in result.headers:
                    response.headers[key] = result.headers[key]
            for cookie in result.raw.headers.getlist('Set-Cookie'):
                response.headers.add('Set-Cookie', cookie)
            return response
        except requests.RequestException:
            return {'error': 'Servicio no disponible'}, 503

    return app


def main():
    servers = [make_server('0.0.0.0', port, create_proxy(port), threaded=True) for port in DESTINATIONS]
    try:
        for server in servers:
            threading.Thread(target=server.serve_forever, daemon=True).start()
        threading.Event().wait()
    finally:
        for server in servers:
            server.shutdown()


if __name__ == '__main__':
    main()
