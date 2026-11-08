import threading
import time
import subprocess
import sys
from pathlib import Path

import pytest
import requests

from lab.app import create_app
from lab.runner import BusyError, LabManager, ResetRequired
from lab.store import RunStore


def manager(tmp_path):
    value = LabManager(tmp_path, {"vulnerable": "http://vulnerable:9001", "secure": "http://secure:9001"}, lambda: "test-control")
    value.control = lambda variant, path, operation_id=None: {"ok": True, "generation": 2, "operation_id": operation_id}
    return value


def client_with_token(app):
    client = app.test_client()
    token = client.get('/lab/api/csrf-token').json['token']
    return client, {"Origin": "http://localhost:5002", "X-CSRF-Token": token}


def test_runner_actions_require_origin_csrf_and_json(tmp_path):
    app = create_app(manager(tmp_path))
    client, headers = client_with_token(app)
    assert client.post('/lab/api/reset', json={}).status_code == 400
    assert client.post('/lab/api/reset', json={}, headers={**headers, "Origin": "http://localhost:5003"}).status_code == 403
    assert client.post('/lab/api/reset', json={}, headers=headers).json['status'] == 'complete'
    assert client.post('/lab/api/runs', json={"case_id": "arbitrary-command", "reset_first": False}, headers=headers).status_code == 400
    assert client.post('/lab/api/runs', json={"case_id": "xss", "command": "anything"}, headers=headers).status_code == 400


def test_partial_reset_blocks_execution_and_retries_both(tmp_path):
    value = manager(tmp_path)
    def partial(variant, path, operation_id=None):
        if variant == 'secure':
            raise requests.ConnectionError()
        return {"ok": True, "generation": 1}
    value.control = partial
    assert value.reset()['status'] == 'partial'
    assert value.needs_reset
    with pytest.raises(ResetRequired):
        value.start('xss')
    value.control = lambda *args, **kwargs: {"ok": True, "generation": 3}
    assert value.reset()['status'] == 'complete'
    assert not value.needs_reset


def test_reset_uses_operation_confirmation_after_lost_response(tmp_path):
    value = manager(tmp_path)
    operations = {}
    def lost(variant, path, operation_id=None):
        if operation_id:
            operations[variant] = operation_id
            raise requests.Timeout()
        return {"ok": True, "generation": 4, "operation_id": operations[variant]}
    value.control = lost
    assert value.reset()['status'] == 'complete'


def test_one_job_and_cancel_keep_honest_evidence(tmp_path):
    value = manager(tmp_path)
    value.reset()
    entered = threading.Event()
    def scenario(run, case, variant):
        entered.set()
        assert value.cancel_event.wait(timeout=3)
        return {"outcome": "inconclusive", "evidence": {"summary": "Cancelada"}}
    value._case_process = scenario
    run = value.start('csrf')
    assert entered.wait(timeout=3)
    with pytest.raises(BusyError):
        value.reset()
    with pytest.raises(BusyError):
        value.start('xss')
    assert value.cancel(run['id'])
    deadline = time.monotonic() + 3
    while value.lock.locked() and time.monotonic() < deadline:
        time.sleep(.01)
    saved = value.store.get(run['id'])
    assert saved['status'] == 'cancelled'
    assert saved['results'][0]['outcome'] == 'inconclusive'
    assert value.needs_reset


def test_history_survives_wallet_reset_and_stays_bounded(tmp_path):
    value = manager(tmp_path)
    for number in range(12):
        value.store.save({"id": f'{number:032x}', "created_at": f'{number:02}', "status": 'completed', 'results': []})
    value.store.prune()
    assert len(value.store.recent()) == 10
    assert len(list((Path(tmp_path) / 'runs').iterdir())) == 10
    value.reset()
    assert len(value.store.recent()) == 10
    with pytest.raises(ValueError):
        value.store.directory('../backend')


def test_restart_marks_unfinished_job_inconclusive(tmp_path):
    value = manager(tmp_path)
    value.store.save({'id': 'a' * 32, 'created_at': '2026', 'status': 'running', 'results': []})
    restarted = manager(tmp_path)
    run = restarted.store.get('a' * 32)
    assert run['status'] == 'error'
    assert 'inconcluso' in run['error']


def test_job_endpoint_never_exposes_non_png_artifacts(tmp_path):
    value = manager(tmp_path)
    run_id = 'a' * 32
    value.store.save({'id': run_id, 'created_at': '2026', 'status': 'completed'})
    app = create_app(value)
    client = app.test_client()
    assert client.get(f'/lab/artifacts/{run_id}/result.json').status_code == 404
    assert client.get(f'/lab/artifacts/{run_id}/../../backend/app.py').status_code == 404


def test_timeout_terminates_real_worker_and_is_not_a_pass(tmp_path, monkeypatch):
    import lab.runner as runner_module
    value = manager(tmp_path)
    original_popen = subprocess.Popen
    processes = []
    def stalled_worker(_command, **kwargs):
        if _command[0] == 'taskkill':
            return original_popen(_command, **kwargs)
        process = original_popen([sys.executable, '-c', 'import time; time.sleep(60)'], **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(runner_module.subprocess, 'Popen', stalled_worker)
    monkeypatch.setattr(runner_module, 'CASE_TIMEOUT_SECONDS', .2)
    run = {'id': 'b' * 32, 'created_at': '2026', 'status': 'running'}
    value.store.save(run)
    result = value._case_process(run, 'csrf', 'vulnerable')
    assert result['outcome'] == 'inconclusive'
    assert 'agotado' in result['evidence']['summary']
    assert processes[0].poll() is not None
