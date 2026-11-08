import hmac
import os
import secrets
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

import requests
from cachelib.file import FileSystemCache
from flask import Flask, abort, g, jsonify, request, send_from_directory, session
from flask_session import Session
from flask_wtf.csrf import CSRFError, CSRFProtect, generate_csrf
from werkzeug.security import check_password_hash, generate_password_hash

DEMO_PASSWORD = 'Demo1234!'
PROVIDER = 'http://quote-provider:8080/quote/USD'
DUMMY_HASH = generate_password_hash('a-dummy-password')


def create_app(config=None):
    app = Flask(__name__, static_folder=None)
    lock = threading.RLock()
    app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY') or secrets.token_hex(32),
        DATABASE=os.environ.get('DATABASE', 'data/wallet.sqlite'),
        SESSION_TYPE='cachelib', SESSION_COOKIE_NAME=os.environ.get('COOKIE_NAME', 'wallet_session'),
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=1800, WTF_CSRF_TIME_LIMIT=1800,
        VARIANT=os.environ.get('VARIANT', 'secure'),
        CONTROL_SECRET=os.environ.get('LAB_CONTROL_TOKEN', ''),
        PROVIDER_URL=os.environ.get('PROVIDER_URL', PROVIDER),
        FRONTEND_DIR=os.environ.get('FRONTEND_DIR', str(Path(__file__).resolve().parent.parent / 'frontend' / 'dist')),
        MAX_CONTENT_LENGTH=16384)
    if config:
        app.config.update(config)
    app._variant = app.config['VARIANT']
    if app._variant not in ('vulnerable', 'secure'):
        raise ValueError('VARIANT debe ser vulnerable o secure')
    teaching = app._variant == 'vulnerable'
    # Intentionally absent only in the isolated teaching instance (exercise CSRF).
    if teaching:
        app.config['WTF_CSRF_ENABLED'] = False
    dbpath = Path(app.config['DATABASE'])
    dbpath.parent.mkdir(parents=True, exist_ok=True)
    cache_dir = Path(app.config.get('SESSION_DIR', str(dbpath.parent / 'sessions')))
    cache_dir.mkdir(parents=True, exist_ok=True)
    app.config['SESSION_CACHELIB'] = FileSystemCache(cache_dir=str(cache_dir), threshold=500)
    Session(app)
    csrf = CSRFProtect(app)

    @contextmanager
    def connect():
        db = sqlite3.connect(app.config['DATABASE'], timeout=5)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys = ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def initialize():
        with lock, connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL, role TEXT NOT NULL, balance_cents INTEGER NOT NULL CHECK(balance_cents >= 0));
            CREATE TABLE IF NOT EXISTS transfers(id INTEGER PRIMARY KEY, sender_id INTEGER NOT NULL REFERENCES users(id),
                recipient_id INTEGER NOT NULL REFERENCES users(id), amount_cents INTEGER NOT NULL,
                concept TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS adjustments(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
                delta_cents INTEGER NOT NULL, reason TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS login_attempts(identity TEXT NOT NULL, at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1), generation INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS reset_operations(operation_id TEXT PRIMARY KEY, generation INTEGER NOT NULL);
            INSERT OR IGNORE INTO settings VALUES(1,0);
            ''')
            if db.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0:
                seed(db)

    def seed(db):
        hashed = generate_password_hash(DEMO_PASSWORD)
        db.executemany('INSERT INTO users(username,password_hash,role,balance_cents) VALUES(?,?,?,?)',
                       [(u, hashed, 'admin' if u == 'admin' else 'user', 100000) for u in ('ana', 'bruno', 'admin')])

    initialize()

    def reset(operation_id=None):
        if not lock.acquire(timeout=10):
            raise TimeoutError('wallet busy')
        try:
            with connect() as db:
                db.execute('BEGIN IMMEDIATE')
                if operation_id:
                    prior = db.execute('SELECT generation FROM reset_operations WHERE operation_id=?', (operation_id,)).fetchone()
                    if prior:
                        return prior['generation']
                db.execute('DELETE FROM transfers')
                db.execute('DELETE FROM adjustments')
                db.execute('DELETE FROM login_attempts')
                db.execute('DELETE FROM users')
                seed(db)
                db.execute('UPDATE settings SET generation = generation + 1 WHERE id=1')
                generation = db.execute('SELECT generation FROM settings WHERE id=1').fetchone()[0]
                if operation_id:
                    db.execute('INSERT INTO reset_operations VALUES(?,?)', (operation_id, generation))
                return generation
        finally:
            lock.release()

    app.reset_wallet = reset
    app.connect_db = connect

    @app.before_request
    def lock_request():
        lock.acquire()
        g.wallet_lock_acquired = True
        origin = request.headers.get('Origin')
        if not teaching and request.path.startswith('/api/') and request.method in ('POST', 'PUT', 'PATCH', 'DELETE') and origin and origin != request.host_url.rstrip('/'):
            return jsonify(error='Origen no permitido'), 403

    @app.teardown_request
    def unlock_request(_error):
        # before_request runs for every request, including exceptions.
        if g.pop('wallet_lock_acquired', False):
            lock.release()

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Cache-Control'] = 'no-store'
        if not teaching:
            response.headers['Content-Security-Policy'] = "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        return response

    @app.errorhandler(CSRFError)
    def csrf_error(_error):
        return jsonify(error='Token CSRF inválido o ausente'), 400

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify(error='No encontrado'), 404

    @app.errorhandler(sqlite3.Error)
    def database_error(_error):
        return jsonify(error='La operación no pudo completarse. Volver a intentar.'), 503

    def payload():
        data = request.get_json(silent=True) if request.is_json else request.form
        return data if isinstance(data, (dict, type(request.form))) else {}

    def current_user():
        uid = session.get('user_id')
        if not uid:
            return None
        with connect() as db:
            generation = db.execute('SELECT generation FROM settings WHERE id=1').fetchone()[0]
            if generation != session.get('generation'):
                session.clear()
                return None
            user = db.execute('SELECT id,username,role,balance_cents FROM users WHERE id=?', (uid,)).fetchone()
            return dict(user) if user else None

    def require_user(admin=False):
        user = current_user()
        if user is None:
            abort(401)
        # Deliberately missing function-level authorization in the teaching app.
        if admin and not teaching and user['role'] != 'admin':
            abort(403)
        return user

    @app.errorhandler(401)
    def unauthorized(_error):
        return jsonify(error='Inicia sesión'), 401

    @app.errorhandler(403)
    def forbidden(_error):
        return jsonify(error='Acceso denegado'), 403

    @app.get('/api/meta')
    def meta():
        return jsonify(variant=app.config['VARIANT'])

    @app.get('/api/csrf-token')
    def csrf_token():
        return jsonify(token=generate_csrf())

    @app.post('/api/auth/register')
    def register():
        data = payload() or {}
        username, password = data.get('username', ''), data.get('password', '')
        if not isinstance(username, str) or not username.isascii() or not username.isalnum() or not 3 <= len(username) <= 32 or not isinstance(password, str) or not 8 <= len(password) <= 128:
            return jsonify(error='Datos inválidos'), 400
        try:
            with connect() as db:
                db.execute('INSERT INTO users(username,password_hash,role,balance_cents) VALUES(?,?,?,0)', (username,generate_password_hash(password),'user'))
        except sqlite3.IntegrityError:
            return jsonify(error='No se pudo registrar'), 409
        return jsonify(user={'username': username}), 201

    @app.post('/api/auth/login')
    def login():
        data = payload() or {}
        username, password = data.get('username', ''), data.get('password', '')
        if not isinstance(username, str) or not isinstance(password, str) or len(username)>128 or len(password)>128:
            return jsonify(error='Credenciales inválidas'), 400
        identities = ('ip:' + (request.remote_addr or 'unknown'), 'account:' + username.lower())
        now = time.time()
        with connect() as db:
            db.execute('DELETE FROM login_attempts WHERE at < ?', (now-60,))
            counts = [db.execute('SELECT COUNT(*) FROM login_attempts WHERE identity=?', (identity,)).fetchone()[0] for identity in identities]
            if not teaching and (counts[0] >= 20 or counts[1] >= 5):
                return jsonify(error='Demasiados intentos'), 429, {'Retry-After':'60'}
            if not teaching:
                db.executemany('INSERT INTO login_attempts VALUES(?,?)', [(identity, now) for identity in identities])
            user = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
            good = check_password_hash(user['password_hash'] if user else DUMMY_HASH, password)
            if not user or not good:
                if teaching:
                    return jsonify(error='Contraseña incorrecta' if user else 'El usuario no existe'), 401
                return jsonify(error='Credenciales inválidas'), 401
            generation = db.execute('SELECT generation FROM settings WHERE id=1').fetchone()[0]
        session.clear()
        session['user_id'] = user['id']
        session['generation'] = generation
        session.permanent = True
        app.session_interface.regenerate(session)
        return jsonify(user={k:user[k] for k in ('id','username','role','balance_cents')})

    @app.post('/api/auth/logout')
    def logout():
        session.clear()
        return jsonify(ok=True)

    @app.get('/api/me')
    def me():
        return jsonify(user=require_user())

    @app.get('/api/movements')
    def movements():
        user = require_user()
        q = request.args.get('q', '')[:200]
        with connect() as db:
            select = '''SELECT t.id,s.username sender,r.username recipient,t.amount_cents,t.concept,t.created_at
                FROM transfers t JOIN users s ON s.id=t.sender_id JOIN users r ON r.id=t.recipient_id '''
            if teaching:
                # SQLi sink is confined to this one educational search endpoint.
                try:
                    rows = db.execute(select + f"WHERE (t.sender_id={user['id']} OR t.recipient_id={user['id']}) AND t.concept LIKE '%{q}%' ORDER BY t.id DESC").fetchall()
                except sqlite3.Error:
                    return jsonify(error='La búsqueda no es válida'), 400
            else:
                rows = db.execute(select + 'WHERE (t.sender_id=? OR t.recipient_id=?) AND t.concept LIKE ? ORDER BY t.id DESC',
                    (user['id'], user['id'], '%'+q+'%')).fetchall()
        return jsonify(movements=[dict(row) for row in rows])

    @app.post('/api/transfers')
    def transfer():
        user = require_user()
        data = payload() or {}
        recipient, concept, amount = data.get('recipient'), data.get('concept', ''), data.get('amount_cents')
        if isinstance(amount, str) and len(amount) <= 9 and amount.isascii() and amount.isdigit():
            amount = int(amount)
        if not isinstance(recipient,str) or not isinstance(concept,str) or len(concept)>200 or type(amount) is not int or not 0 < amount <= 100000000:
            return jsonify(error='Datos inválidos'), 400
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            target = db.execute('SELECT id FROM users WHERE username=?', (recipient,)).fetchone()
            if not target or target['id'] == user['id']:
                return jsonify(error='Destinatario inválido'), 400
            changed = db.execute('UPDATE users SET balance_cents=balance_cents-? WHERE id=? AND balance_cents>=?', (amount,user['id'],amount)).rowcount
            if not changed:
                return jsonify(error='Saldo insuficiente'), 409
            db.execute('UPDATE users SET balance_cents=balance_cents+? WHERE id=?', (amount,target['id']))
            db.execute('INSERT INTO transfers(sender_id,recipient_id,amount_cents,concept) VALUES(?,?,?,?)', (user['id'],target['id'],amount,concept))
        return jsonify(ok=True)

    @app.get('/api/admin/users')
    def admin_users():
        require_user(admin=True)
        with connect() as db:
            users = [dict(x) for x in db.execute('SELECT id,username,role,balance_cents FROM users ORDER BY id')]
        return jsonify(users=users)

    @app.post('/api/admin/adjustments')
    def adjust():
        require_user(admin=True)
        data = payload() or {}
        uid, delta, reason = data.get('user_id'), data.get('delta_cents'), data.get('reason')
        if type(uid) is not int or type(delta) is not int or not -100000000 <= delta <= 100000000 or delta == 0 or not isinstance(reason,str) or not 1<=len(reason)<=200:
            return jsonify(error='Datos inválidos'), 400
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('UPDATE users SET balance_cents=balance_cents+? WHERE id=? AND balance_cents+?>=0', (delta,uid,delta)).rowcount:
                return jsonify(error='Ajuste inválido'), 400
            db.execute('INSERT INTO adjustments(user_id,delta_cents,reason) VALUES(?,?,?)',(uid,delta,reason))
        return jsonify(ok=True)

    @app.post('/api/quotes/import')
    def quote():
        require_user()
        data = payload() or {}
        supplied = data.get('url')
        destination = app.config['PROVIDER_URL']
        if teaching:
            # Containment applies even to the intentionally vulnerable instance:
            # it can reach only the two fictitious services, never the user's host.
            if not isinstance(supplied, str) or len(supplied) > 512:
                return jsonify(error='Destino fuera del laboratorio'), 400
            try:
                parsed = urlsplit(supplied)
                contained = (parsed.scheme == 'http' and parsed.netloc in ('quote-provider:8080', 'private-ledger:8080')
                             and not parsed.username and not parsed.password and not parsed.fragment)
            except ValueError:
                contained = False
            if not contained:
                return jsonify(error='Destino fuera del laboratorio'), 400
            destination = supplied
        elif supplied != PROVIDER:
            return jsonify(error='Proveedor no permitido'), 400
        try:
            with requests.Session() as client:
                client.trust_env = False
                with client.get(destination, timeout=(2,2), allow_redirects=False, stream=True) as response:
                    if response.status_code != 200 or response.headers.get('Content-Type','').split(';')[0].strip() != 'application/json':
                        raise ValueError('invalid response')
                    body = b''
                    deadline = time.monotonic() + 5
                    # Check the total deadline even if a peer trickles single bytes.
                    # The entire accepted response is only 8 KiB.
                    for chunk in response.iter_content(1):
                        if time.monotonic() > deadline:
                            raise ValueError('response deadline exceeded')
                        body += chunk
                        if len(body) > 8192:
                            raise ValueError('response too large')
                    import json
                    result = json.loads(body)
                    if not teaching and (not isinstance(result,dict) or result.get('currency') != 'USD' or type(result.get('rate_cents')) is not int or not 0 < result['rate_cents'] <= 100000000):
                        raise ValueError('invalid quote')
            return jsonify(result=result)
        except (requests.RequestException, ValueError):
            return jsonify(error='Proveedor no disponible'), 502

    @app.get('/')
    @app.get('/<path:path>')
    def frontend(path='index.html'):
        root = Path(app.config['FRONTEND_DIR'])
        if (root / path).is_file():
            return send_from_directory(root, path)
        if (root / 'index.html').is_file() and not path.startswith('api/'):
            return send_from_directory(root, 'index.html')
        return jsonify(error='Interfaz no compilada'), 404

    return app


def create_control_app(wallet):
    control = Flask('wallet_control')
    control.config['MAX_CONTENT_LENGTH'] = 4096

    @control.errorhandler(sqlite3.Error)
    def database_error(_error):
        return jsonify(error='No se pudo confirmar la operación de mantenimiento'), 503

    @control.post('/internal/reset')
    def reset_wallet():
        token = request.headers.get('Authorization', '')
        expected = wallet.config['CONTROL_SECRET']
        if not expected or not hmac.compare_digest(token, 'Bearer '+expected):
            return jsonify(error='No autorizado'), 403
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict) or set(data) != {'operation_id'}:
            return jsonify(error='Parámetros de mantenimiento inválidos'), 400
        operation_id = data.get('operation_id')
        try:
            uuid.UUID(operation_id)
        except (ValueError, TypeError, AttributeError):
            return jsonify(error='operation_id inválido'), 400
        try:
            generation = wallet.reset_wallet(operation_id)
        except TimeoutError:
            return jsonify(error='Billetera ocupada'), 503
        return jsonify(ok=True, generation=generation, operation_id=operation_id)

    @control.get('/internal/status')
    def status():
        expected = wallet.config['CONTROL_SECRET']
        if not expected or not hmac.compare_digest(request.headers.get('Authorization', ''), 'Bearer '+expected):
            return jsonify(error='No autorizado'), 403
        with wallet.connect_db() as db:
            generation = db.execute('SELECT generation FROM settings WHERE id=1').fetchone()[0]
            operation = db.execute('SELECT operation_id FROM reset_operations ORDER BY rowid DESC LIMIT 1').fetchone()
        return jsonify(ok=True, generation=generation, operation_id=operation['operation_id'] if operation else None)

    return control
