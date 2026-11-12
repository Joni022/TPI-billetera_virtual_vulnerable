import concurrent.futures
import time
import uuid

import pytest

from backend.app import create_app, create_control_app


@pytest.fixture
def wallet(tmp_path):
    return create_app({'TESTING': True, 'SECRET_KEY':'test-key', 'DATABASE':str(tmp_path/'db.sqlite'),
                       'SESSION_DIR':str(tmp_path/'sessions'), 'CONTROL_SECRET':'test-control'})


def token(client):
    return client.get('/api/csrf-token').json['token']


def login(client, username='ana'):
    response = client.post('/api/auth/login', json={'username':username,'password':'Demo1234!'}, headers={'X-CSRF-Token': token(client)})
    assert response.status_code == 200


def post(client, path, data):
    return client.post(path, json=data, headers={'X-CSRF-Token':token(client)})


def test_transfer_and_access_control(wallet):
    client = wallet.test_client()
    login(client)
    assert client.post('/api/transfers', json={}).status_code == 400
    assert client.get('/api/admin/users').status_code == 403
    assert post(client, '/api/admin/adjustments', {'user_id':2,'delta_cents':100,'reason':'test'}).status_code == 403
    assert post(client, '/api/transfers', {'recipient':'bruno','amount_cents':150,'concept':'hello'}).status_code == 200
    assert client.get('/api/me').json['user']['balance_cents'] == 99850
    assert client.get('/api/movements').json['movements'][0]['concept'] == 'hello'
    assert not client.get('/api/movements?q=%27%20OR%201%3D1--').json['movements']
    assert post(client, '/api/transfers', {'recipient':'bruno','amount_cents':999999,'concept':'x'}).status_code == 409
    assert client.get('/api/me').json['user']['balance_cents'] == 99850


@pytest.mark.parametrize('variant', ['vulnerable', 'secure'])
def test_movement_search_quote_and_normal_query(tmp_path, variant):
    wallet = create_app({'TESTING': True, 'VARIANT': variant, 'SECRET_KEY': 'test-key',
                         'DATABASE': str(tmp_path/'db.sqlite'), 'SESSION_DIR': str(tmp_path/'sessions')})
    client = wallet.test_client()
    login(client)
    assert post(client, '/api/transfers', {'recipient': 'bruno', 'amount_cents': 100, 'concept': 'Compra propia'}).status_code == 200
    assert client.get('/api/movements', query_string={'q': 'Compra propia'}).json['movements'][0]['concept'] == 'Compra propia'
    response = client.get('/api/movements', query_string={'q': "'"})
    if variant == 'vulnerable':
        assert response.status_code == 400
        assert response.json['error'].startswith('Error de base de datos: ')
        assert 'syntax error' in response.json['error'] or 'unrecognized token' in response.json['error']
    else:
        assert response.status_code == 200
        assert response.json == {'movements': []}


def test_transfer_rejects_oversized_form_amount_without_changes(wallet):
    client = wallet.test_client()
    login(client)
    before = client.get('/api/me').json['user']['balance_cents']
    response = client.post('/api/transfers', data={
        'recipient': 'bruno', 'amount_cents': '9' * 5000,
        'concept': 'prueba', 'csrf_token': token(client),
    })
    assert response.status_code == 400
    assert client.get('/api/me').json['user']['balance_cents'] == before
    with wallet.connect_db() as db:
        assert db.execute("SELECT balance_cents FROM users WHERE username='bruno'").fetchone()[0] == 100000
        assert db.execute('SELECT COUNT(*) FROM transfers').fetchone()[0] == 0


def test_login_limit_and_uniform_errors(wallet):
    client = wallet.test_client()
    csrf = token(client)
    def attempt(username):
        return client.post('/api/auth/login', json={'username':username,'password':'wrong'}, headers={'X-CSRF-Token':csrf})
    assert attempt('ana').json == attempt('missing').json
    for _ in range(4):
        assert attempt('missing').status_code == 401
    limited = attempt('missing')
    assert limited.status_code == 429 and limited.headers['Retry-After'] == '60'


def test_reset_private_idempotent_and_session_invalidated(wallet):
    client = wallet.test_client()
    login(client)
    control = create_control_app(wallet).test_client()
    op = str(uuid.uuid4())
    assert control.post('/internal/reset', json={'operation_id':op}).status_code == 403
    headers = {'Authorization':'Bearer test-control'}
    r1 = control.post('/internal/reset', json={'operation_id':op}, headers=headers)
    r2 = control.post('/internal/reset', json={'operation_id':op}, headers=headers)
    assert r1.json == r2.json
    assert control.get('/internal/status', headers=headers).json['generation'] == r1.json['generation']
    assert client.get('/api/me').status_code == 401


def test_logout_revokes_previous_cookie(wallet):
    client = wallet.test_client()
    login(client)
    old = client.get_cookie(wallet.config['SESSION_COOKIE_NAME']).value
    assert post(client, '/api/auth/logout', {}).status_code == 200
    client.set_cookie(wallet.config['SESSION_COOKIE_NAME'], old)
    assert client.get('/api/me').status_code == 401


def test_admin_and_quote_block(wallet):
    client = wallet.test_client()
    login(client, 'admin')
    assert len(client.get('/api/admin/users').json['users']) == 3
    assert post(client, '/api/admin/adjustments', {'user_id':2,'delta_cents':10,'reason':'demo'}).status_code == 200
    assert post(client, '/api/quotes/import', {'url':'http://private-ledger:8080/demo'}).status_code == 400


def test_concurrent_transfers_preserve_balance(wallet):
    def transfer(_):
        c = wallet.test_client()
        login(c)
        return post(c, '/api/transfers', {'recipient':'bruno','amount_cents':60000,'concept':'parallel'}).status_code
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(transfer, range(2)))
    assert sorted(results) == [200, 409]
    with wallet.connect_db() as db:
        balances = db.execute('SELECT sum(balance_cents) FROM users').fetchone()[0]
        assert balances == 300000


def test_origin_malformed_and_hidden_hash(wallet):
    client = wallet.test_client()
    t = token(client)
    response = client.post('/api/auth/login', json={'username':'ana','password':'Demo1234!'},
                           headers={'Origin':'http://evil.invalid','X-CSRF-Token':t})
    assert response.status_code == 403
    login(client)
    assert 'password' not in str(client.get('/api/me').json)
    for amount in (True, -1, 0, 1.5, None, 10**100):
        assert post(client, '/api/transfers', {'recipient':'bruno','amount_cents':amount,'concept':'x'}).status_code == 400
    assert post(client, '/api/transfers', {'recipient':'ana','amount_cents':10,'concept':'x'}).status_code == 400


def test_session_expires(tmp_path):
    wallet = create_app({'TESTING':True, 'SECRET_KEY':'test', 'DATABASE':str(tmp_path/'expire.db'),
                         'SESSION_DIR':str(tmp_path/'sessions'), 'PERMANENT_SESSION_LIFETIME':1})
    client = wallet.test_client()
    login(client)
    assert client.get('/api/me').status_code == 200
    time.sleep(2.1)
    assert client.get('/api/me').status_code == 401


def test_provider_errors_and_valid_response(wallet, monkeypatch):
    import requests
    client = wallet.test_client()
    login(client)

    class Response:
        status_code = 200
        headers = {'Content-Type':'application/json'}
        content = b'{"currency":"USD","rate_cents":10}'
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def iter_content(self, _size): yield self.content

    class Session:
        trust_env = True
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, *args, **kwargs):
            assert kwargs['allow_redirects'] is False
            return Response()

    monkeypatch.setattr(requests, 'Session', Session)
    url = {'url':'http://quote-provider:8080/quote/USD'}
    assert post(client, '/api/quotes/import', url).json['result']['rate_cents'] == 10
    monkeypatch.setattr(Response, 'content', b'x' * 8193)
    assert post(client, '/api/quotes/import', url).status_code == 502
    monkeypatch.setattr(Response, 'status_code', 302)
    assert post(client, '/api/quotes/import', url).status_code == 502
    def timeout(*args, **kwargs): raise requests.Timeout()
    monkeypatch.setattr(Session, 'get', timeout)
    assert post(client, '/api/quotes/import', url).status_code == 502


def test_rate_limit_per_address_across_accounts(wallet):
    client = wallet.test_client()
    csrf = token(client)
    for i in range(20):
        r = client.post('/api/auth/login', json={'username':f'absent{i}','password':'wrong'}, headers={'X-CSRF-Token':csrf})
        assert r.status_code == 401
    limited = client.post('/api/auth/login', json={'username':'other','password':'wrong'}, headers={'X-CSRF-Token':csrf})
    assert limited.status_code == 429
    assert limited.headers['Retry-After'] == '60'


def test_registration_and_malformed_json(wallet):
    client = wallet.test_client()
    csrf = token(client)
    headers = {'X-CSRF-Token':csrf}
    assert client.post('/api/auth/register', json=['not','an','object'], headers=headers).status_code == 400
    assert client.post('/api/auth/register', json={'username':'nuevo','password':'contrasena123'}, headers=headers).status_code == 201
    assert client.post('/api/auth/register', json={'username':'nuevo','password':'contrasena123'}, headers=headers).status_code == 409
    assert client.post('/api/auth/login', json={'username':'nuevo','password':'contrasena123'}, headers=headers).status_code == 200
    assert client.get('/api/me').json['user']['balance_cents'] == 0


def test_gateway_forwards_cookies_without_sharing(monkeypatch):
    from backend.gateway import create_proxy
    import requests
    seen = []

    class Headers:
        def getlist(self, name):
            return ['one=1; Path=/', 'two=2; Path=/'] if name == 'Set-Cookie' else []

    class Result:
        status_code = 200
        content = b'{}'
        headers = {'Content-Type': 'application/json', 'Cache-Control': 'no-store'}
        raw = type('Raw', (), {'headers': Headers()})()

    class Session:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def request(self, method, url, **kwargs):
            seen.append((self, method, url, kwargs))
            return Result()

    monkeypatch.setattr(requests, 'Session', Session)
    client = create_proxy(5000).test_client()
    result = client.get('/api/me?test=1')
    client.get('/api/me')
    assert result.status_code == 200
    assert len(result.headers.getlist('Set-Cookie')) == 2
    assert result.headers['Cache-Control'] == 'no-store'
    assert seen[0][0] is not seen[1][0]
    assert seen[0][2] == 'http://vulnerable:5000/api/me'
    assert seen[0][3]['headers']['Host'] == 'localhost:5000'
    assert seen[0][3]['allow_redirects'] is False
