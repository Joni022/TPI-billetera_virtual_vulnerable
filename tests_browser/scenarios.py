"""Pruebas de navegador para CSRF y XSS persistente en las billeteras visibles.

Estas funciones usan las pantallas y las rutas públicas reales de la billetera.
No leen cookies de la sesión humana ni llaman a endpoints de prueba.
"""

from __future__ import annotations

import threading
import time
import traceback
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


DEMO_USER = "ana"
DEMO_PASSWORD = "Demo1234!"
XSS_CONCEPT = """<img src=x onerror="document.body.insertAdjacentHTML('afterbegin','<div data-testid=&quot;xss-marker&quot; style=&quot;color:red;font-weight:bold&quot;>XSS ejecutado</div>');this.remove()">"""
PAGE_TIMEOUT_MS = 12_000
ACTION_TIMEOUT_MS = 8_000


def _result(outcome: str, summary: str, **evidence: Any) -> dict[str, Any]:
    record = {"summary": summary}
    record.update(evidence)
    return {"outcome": outcome, "evidence": record}


def _safe_request(request: Any, status: int | None = None) -> dict[str, Any]:
    """Keep useful request facts while excluding cookies and anti-CSRF tokens."""
    parsed = urlsplit(request.url)
    source_headers = request.headers
    headers = {
        name: source_headers[name]
        for name in ("content-type", "origin", "referer")
        if name in source_headers
    }
    body = request.post_data
    if body and len(body) > 1200:
        body = body[:1200] + "… [truncado]"
    value: dict[str, Any] = {
        "method": request.method,
        "path": parsed.path,
        "headers": headers,
    }
    if body is not None:
        value["body"] = body
    if status is not None:
        value["status"] = status
    return value


def _wallet_snapshot(page: Any) -> dict[str, Any]:
    """Read only the signed-in user's balance and visible activity."""
    return page.evaluate(
        """async () => {
          const [accountResponse, movementsResponse] = await Promise.all([
            fetch('/api/me', { credentials: 'include', cache: 'no-store' }),
            fetch('/api/movements', { credentials: 'include', cache: 'no-store' })
          ]);
          const account = accountResponse.ok ? await accountResponse.json() : null;
          const movements = movementsResponse.ok ? await movementsResponse.json() : null;
          return {
            account_status: accountResponse.status,
            username: account?.user?.username ?? null,
            balance_cents: account?.user?.balance_cents ?? null,
            movement_count: Array.isArray(movements?.movements) ? movements.movements.length : null,
            latest_concept: Array.isArray(movements?.movements) && movements.movements.length
              ? movements.movements[0].concept
              : null
          };
        }"""
    )


def _login(page: Any, base_url: str, username: str = DEMO_USER) -> None:
    page.goto(base_url.rstrip("/") + "/", wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
    page.get_by_test_id("username").fill(username)
    page.get_by_test_id("password").fill(DEMO_PASSWORD)
    page.get_by_test_id("login-submit").click()
    page.get_by_test_id("balance").wait_for(state="visible", timeout=ACTION_TIMEOUT_MS)


def _valid_snapshot(snapshot: dict[str, Any], username: str) -> bool:
    return (
        snapshot.get("account_status") == 200
        and snapshot.get("username") == username
        and isinstance(snapshot.get("balance_cents"), int)
        and isinstance(snapshot.get("movement_count"), int)
    )


def _write_screenshot(page: Any, directory: Path, name: str) -> str:
    path = directory / name
    page.screenshot(path=str(path), full_page=True, animations="disabled", timeout=ACTION_TIMEOUT_MS)
    return name


def _is_cancelled(cancel_event: threading.Event) -> bool:
    return cancel_event.is_set()


def _load_playwright():
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None, None
    return sync_playwright, PlaywrightTimeoutError


def run_browser_case(
    case_id: str,
    variant: str,
    base_url: str,
    attacker_url: str,
    artifact_dir: str | Path,
    cancel_event: threading.Event,
) -> dict[str, Any]:
    """Run a browser scenario for one variant and return JSON-serializable evidence."""
    if case_id not in ("csrf", "xss"):
        return _result("unexpected", "Este ejecutor sólo implementa los casos csrf y xss.")
    if variant not in ("vulnerable", "secure"):
        return _result("unexpected", "La variante indicada no es válida.")

    directory = Path(artifact_dir)
    directory.mkdir(parents=True, exist_ok=True)
    sync_playwright, playwright_timeout = _load_playwright()
    if sync_playwright is None or playwright_timeout is None:
        return _result(
            "inconclusive",
            "Playwright no está instalado en el entorno del ejecutor.",
            request=None,
            before=None,
            after=None,
            screenshots=[],
        )

    playwright_manager = sync_playwright()
    playwright = playwright_manager.start()
    browser = None
    contexts: list[Any] = []
    try:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 960},
            reduced_motion="reduce",
            service_workers="block",
        )
        contexts.append(context)
        page = context.new_page()
        page.set_default_timeout(ACTION_TIMEOUT_MS)
        request_log: list[dict[str, Any]] = []
        response_log: list[dict[str, Any]] = []

        def capture_request(request: Any) -> None:
            if request.method == "POST" and urlsplit(request.url).path == "/api/transfers":
                request_log.append(_safe_request(request))

        def capture_response(response: Any) -> None:
            request = response.request
            if request.method == "POST" and urlsplit(request.url).path == "/api/transfers":
                response_log.append(_safe_request(request, response.status))

        def attach_capture(target_page: Any) -> None:
            target_page.on("request", capture_request)
            target_page.on("response", capture_response)

        attach_capture(page)
        context.on("page", attach_capture)

        if _is_cancelled(cancel_event):
            return _result("inconclusive", "La prueba se canceló antes de iniciar el navegador.")

        _login(page, base_url)
        before = _wallet_snapshot(page)
        if not _valid_snapshot(before, DEMO_USER):
            return _result("inconclusive", "La sesión de ana no quedó activa; puede haberse restablecido la billetera.", before=before, screenshots=[])
        before_screenshot = _write_screenshot(page, directory, "before.png")

        if case_id == "csrf":
            attack_url = attacker_url.rstrip("/") + "/?variant=" + variant
            attacker_page = context.new_page()
            try:
                attacker_page.goto(attack_url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
            except playwright_timeout:
                # A form auto-submit can navigate before goto() returns.
                pass
            deadline = time.monotonic() + 10
            while not any(entry["path"] == "/api/transfers" for entry in response_log) and time.monotonic() < deadline:
                attacker_page.wait_for_timeout(100)

            transfer_record = next(
                (entry for entry in reversed(response_log) if entry["path"] == "/api/transfers"),
                None,
            )
            transfer_request = next(
                (entry for entry in reversed(request_log) if entry["path"] == "/api/transfers"),
                None,
            )

            if _is_cancelled(cancel_event):
                return _result(
                    "inconclusive",
                    "La prueba se canceló durante el envío del formulario atacante.",
                    request=transfer_record or transfer_request,
                    before=before,
                    after=None,
                    screenshots=[before_screenshot],
                )

            visible_balance_before = page.get_by_test_id("balance").inner_text()
            page.bring_to_front()
            status = transfer_record.get("status") if transfer_record else None
            if status == 200:
                expected_balance = before["balance_cents"] - 2500
                try:
                    page.wait_for_function(
                        """async (expected) => {
                          const response = await fetch('/api/me', {credentials: 'include', cache: 'no-store'});
                          if (!response.ok) return false;
                          const payload = await response.json();
                          const visible = document.querySelector('[data-testid=balance]')?.textContent?.trim();
                          return payload.user?.balance_cents === expected && visible && visible !== previous;
                        }""",
                        arg={"expected": expected_balance, "previous": visible_balance_before},
                        timeout=6500,
                    )
                except playwright_timeout:
                    pass
            else:
                # Let the wallet's two-second refresh show any unchanged balance.
                page.wait_for_timeout(2200)
            after = _wallet_snapshot(page)
            after_screenshot = _write_screenshot(page, directory, "after.png")

            request_evidence = transfer_record or transfer_request
            if request_evidence is None:
                return _result(
                    "inconclusive",
                    "La página atacante no produjo una solicitud de transferencia observable.",
                    request=None,
                    before=before,
                    after=after,
                    screenshots=[before_screenshot, after_screenshot],
                )

            if not _valid_snapshot(after, DEMO_USER):
                outcome = "inconclusive"
                summary = "La sesión de ana terminó durante la prueba; puede haberse restablecido la billetera."
            else:
                delta = before["balance_cents"] - after["balance_cents"]
                before_count = before["movement_count"]
                after_count = after["movement_count"]
                attack_visible = after.get("latest_concept") == "Demostración CSRF"
                no_change = delta == 0 and after_count == before_count
                attack_effect = delta == 2500 and after_count == before_count + 1 and attack_visible
                if variant == "vulnerable" and status == 200 and attack_effect:
                    outcome = "attack_reproduced"
                    summary = "El formulario de :5003 transfirió $25 y el saldo de ana disminuyó."
                elif variant == "secure" and status in (400, 403) and no_change:
                    outcome = "blocked"
                    summary = "La billetera corregida rechazó la transferencia entre orígenes y no cambió saldo ni actividad."
                elif variant == "vulnerable" and status in (400, 403) and no_change:
                    outcome = "unexpected"
                    summary = "La variante vulnerable rechazó el formulario atacante; no se reprodujo la conducta esperada."
                elif variant == "secure" and status == 200 and attack_effect:
                    outcome = "unexpected"
                    summary = "La variante corregida aceptó la transferencia entre orígenes."
                else:
                    outcome = "inconclusive"
                    summary = "Saldo o actividad cambiaron de forma distinta a la operación del escenario; puede haber interferencia."
            return _result(
                outcome,
                summary,
                request=request_evidence,
                before=before,
                after=after,
                screenshots=[before_screenshot, after_screenshot],
            )

        # Persistent XSS: sender and recipient use isolated browser contexts.
        receiver_context = browser.new_context(
            viewport={"width": 1440, "height": 960},
            reduced_motion="reduce",
            service_workers="block",
        )
        contexts.append(receiver_context)
        receiver_page = receiver_context.new_page()
        receiver_page.set_default_timeout(ACTION_TIMEOUT_MS)
        _login(receiver_page, base_url, "bruno")
        receiver_before = _wallet_snapshot(receiver_page)
        if not _valid_snapshot(receiver_before, "bruno"):
            return _result("inconclusive", "La sesión independiente de bruno no quedó activa.", before=receiver_before, screenshots=[])
        before_screenshot = _write_screenshot(receiver_page, directory, "before.png")

        if _is_cancelled(cancel_event):
            return _result(
                "inconclusive",
                "La prueba se canceló antes de enviar la transferencia.",
                before=receiver_before,
                screenshots=[before_screenshot],
            )

        page.get_by_role("button", name="Transferencias", exact=True).click()
        page.get_by_test_id("transfer-recipient").fill("bruno")
        page.get_by_test_id("transfer-amount").fill("1")
        page.get_by_test_id("transfer-concept").fill(XSS_CONCEPT)
        with page.expect_response(
            lambda response: response.request.method == "POST"
            and urlsplit(response.url).path == "/api/transfers",
            timeout=PAGE_TIMEOUT_MS,
        ) as transfer_response_info:
            page.get_by_test_id("transfer-submit").click()
        transfer_response = transfer_response_info.value
        if _is_cancelled(cancel_event):
            return _result(
                "inconclusive",
                "La prueba se canceló después de enviar la transferencia.",
                request=_safe_request(transfer_response.request, transfer_response.status),
                before=receiver_before,
                after=None,
                screenshots=[before_screenshot],
            )
        if transfer_response.status != 200:
            return _result(
                "inconclusive",
                "La transferencia de prueba no se completó; puede haber cambiado la sesión o el estado de la billetera.",
                request=_safe_request(transfer_response.request, transfer_response.status),
                before=receiver_before,
                after=_wallet_snapshot(receiver_page),
                screenshots=[before_screenshot],
            )

        receiver_page.get_by_role("button", name="Actividad", exact=True).click()
        receiver_page.wait_for_function(
            """async (expected) => {
                  const response = await fetch('/api/movements', {credentials: 'include', cache: 'no-store'});
                  if (!response.ok) return false;
                  const payload = await response.json();
                  return payload.movements?.some((movement) => movement.concept === expected) === true;
                }""",
            arg=XSS_CONCEPT,
            timeout=ACTION_TIMEOUT_MS,
        )
        receiver_page.get_by_test_id("movements-list").wait_for(state="visible", timeout=ACTION_TIMEOUT_MS)

        after = _wallet_snapshot(receiver_page)
        if not _valid_snapshot(after, "bruno"):
            return _result(
                "inconclusive",
                "La sesión de bruno terminó durante la prueba; puede haberse restablecido la billetera.",
                request=_safe_request(transfer_response.request, transfer_response.status),
                before=receiver_before,
                after=after,
                screenshots=[before_screenshot],
            )
        if (
            after["balance_cents"] != receiver_before["balance_cents"] + 100
            or after["movement_count"] != receiver_before["movement_count"] + 1
            or after.get("latest_concept") != XSS_CONCEPT
        ):
            return _result(
                "inconclusive",
                "El saldo o la actividad de bruno no refleja sólo la transferencia de prueba; puede haber interferencia.",
                request=_safe_request(transfer_response.request, transfer_response.status),
                before=receiver_before,
                after=after,
                screenshots=[before_screenshot],
            )

        if variant == "vulnerable":
            receiver_page.wait_for_function(
                """() => document.querySelector('[data-testid=xss-marker]')?.textContent === 'XSS ejecutado'""",
                timeout=ACTION_TIMEOUT_MS,
            )
            outcome = "attack_reproduced"
            summary = "Bruno abrió Actividad y el concepto persistente creó un marcador visible «XSS ejecutado»."
        else:
            receiver_page.get_by_test_id("wallet-heading").wait_for(state="visible", timeout=ACTION_TIMEOUT_MS)
            rendered_text = receiver_page.get_by_test_id("movements-list").inner_text()
            visible_marker = receiver_page.get_by_test_id("xss-marker").count()
            if XSS_CONCEPT in rendered_text and visible_marker == 0:
                outcome = "blocked"
                summary = "Bruno vio el concepto como texto y no se creó el marcador."
            else:
                outcome = "unexpected"
                summary = "El concepto no se comportó como texto seguro en la variante corregida."

        after_screenshot = _write_screenshot(receiver_page, directory, "after.png")
        request_evidence = next(
            (entry for entry in reversed(request_log) if entry["path"] == "/api/transfers"),
            None,
        ) or _safe_request(transfer_response.request, transfer_response.status)
        request_evidence["status"] = transfer_response.status
        return _result(
            outcome,
            summary,
            request=request_evidence,
            before=receiver_before,
            after=after,
            screenshots=[before_screenshot, after_screenshot],
        )

    except playwright_timeout:
        return _result(
            "inconclusive",
            "La prueba superó el tiempo de espera antes de obtener una evidencia completa.",
            screenshots=[
                name
                for name in ("before.png", "after.png")
                if (directory / name).is_file()
            ],
        )
    except Exception as error:
        # Do not serialize exception text; browser errors can contain URLs or request details.
        frames = traceback.extract_tb(error.__traceback__)
        return _result(
            "inconclusive",
            "No se pudo completar la prueba en el navegador. Comprobá las billeteras y el servicio atacante.",
            diagnostic={
                "error_type": type(error).__name__,
                "frames": [
                    {"file": Path(frame.filename).name, "line": frame.lineno}
                    for frame in frames[-8:]
                ],
            },
            screenshots=[
                name
                for name in ("before.png", "after.png")
                if (directory / name).is_file()
            ],
        )
    finally:
        for browser_context in reversed(contexts):
            try:
                browser_context.close()
            except Exception:
                pass
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        try:
            playwright_manager.stop()
        except Exception:
            pass
