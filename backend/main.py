import os
import threading
from pathlib import Path

from waitress import serve

from backend.app import create_app, create_control_app


def main():
    token_file = os.environ.get('LAB_CONTROL_TOKEN_FILE')
    config = {}
    if token_file:
        config['CONTROL_SECRET'] = Path(token_file).read_text(encoding='utf-8').strip()
    app = create_app(config)
    control = create_control_app(app)
    threading.Thread(target=serve, args=(control,), kwargs={'host': '0.0.0.0', 'port': 9001, 'threads': 2}, daemon=True).start()
    serve(app, host='0.0.0.0', port=int(os.environ.get('PORT', '5000')), threads=4)


if __name__ == '__main__':
    main()
