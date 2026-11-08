"""Read-only visual/layout smoke checks for the local Umbral app.

Usage inside the lab container:
    python -m tests_browser.visual_smoke --output /state/visual

The only wallet POST is a browser-routed fake 401 used to inspect the login
error state. No wallet data is modified. The real demo login is read-only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from playwright.sync_api import Page, sync_playwright


WALLETS = {
    "vulnerable": "http://localhost:5000",
    "secure": "http://localhost:5001",
}
GUIDE_URL = "http://localhost:5002"
DEMO_USER = "ana"
DEMO_PASSWORD = "Demo1234!"
VIEWPORTS = {
    "desktop": {"width": 1440, "height": 1000},
    "mobile": {"width": 390, "height": 844},
}


def _attach_browser_log(page: Page, report: dict[str, Any]) -> None:
    authenticated = {"value": False}
    def response_received(response):
        if urlsplit(response.url).path == '/api/auth/login' and response.status == 200:
            authenticated['value'] = True
    page.on('response', response_received)
    def console_received(message):
        if message.type != 'error':
            return
        path = urlsplit(message.location.get('url', '')).path
        expected_auth_error = ('401' in message.text and
                               (path == '/api/auth/login' or (path == '/api/me' and not authenticated['value'])))
        if expected_auth_error:
            report.setdefault('expected_auth_console', []).append({'path': path, 'status': 401})
        else:
            report['console_errors'].append(message.text)
    page.on('console', console_received)
    page.on("pageerror", lambda error: report["page_errors"].append(str(error)))


def _overflow(page: Page, report: dict[str, Any], label: str) -> None:
    value = page.evaluate(
        """() => ({
          viewport: document.documentElement.clientWidth,
          document: document.documentElement.scrollWidth,
          body: document.body.scrollWidth
        })"""
    )
    value["horizontal_overflow"] = value["document"] > value["viewport"] + 1 or value["body"] > value["viewport"] + 1
    report["layouts"][label] = value


def _focus_visible(page: Page) -> dict[str, Any]:
    page.bring_to_front()
    page.keyboard.press("Tab")
    page.wait_for_function("""() => {
      const element = document.activeElement;
      if (!document.hasFocus() || !element?.matches(':focus-visible')) return false;
      const style = getComputedStyle(element);
      return style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0;
    }""", timeout=3000)
    return page.evaluate(
        """() => {
          const element = document.activeElement;
          const style = element ? getComputedStyle(element) : null;
          return {
            tag: element?.tagName ?? null,
            label: element?.getAttribute('aria-label') || element?.textContent?.trim().slice(0, 80) || null,
            outline_style: style?.outlineStyle ?? null,
            outline_width: style?.outlineWidth ?? null,
            focus_visible: Boolean(style && style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0)
          };
        }"""
    )


def _save(page: Page, output: Path, name: str, *, full_page: bool = False) -> str:
    path = output / name
    page.screenshot(path=str(path), full_page=full_page, animations="disabled")
    return name


def _check_guide(browser: Any, output: Path, report: dict[str, Any]) -> None:
    for size_name, viewport in VIEWPORTS.items():
        context = browser.new_context(viewport=viewport, reduced_motion="reduce", locale="es-AR")
        page = context.new_page()
        _attach_browser_log(page, report)
        page.goto(GUIDE_URL + "/", wait_until="domcontentloaded", timeout=20_000)
        page.get_by_role("heading", name="Seguridad, vista desde adentro.").wait_for(state="visible")
        _overflow(page, report, f"guide-{size_name}-top")
        report["focus"][f"guide-{size_name}"] = _focus_visible(page)
        _save(page, output, f"guide-{size_name}.png")

        reset_button = page.get_by_role("button", name="Restablecer ambas versiones", exact=True)
        if reset_button.is_enabled():
            reset_button.click()
            dialog = page.get_by_role("dialog")
            dialog.wait_for(state="visible")
            page.keyboard.press("Tab")
            report["focus"][f"guide-{size_name}-dialog"] = page.evaluate(
                """() => {
                  const element = document.activeElement;
                  const style = element ? getComputedStyle(element) : null;
                  return {
                    tag: element?.tagName ?? null,
                    label: element?.textContent?.trim().slice(0, 80) || null,
                    outline_style: style?.outlineStyle ?? null,
                    outline_width: style?.outlineWidth ?? null,
                    focus_visible: Boolean(style && style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0)
                  };
                }"""
            )
            page.keyboard.press("Escape")
            dialog.wait_for(state="hidden")

        for section_name, selector in (
            ("practice", ".practice-section"),
            ("evidence", ".results-section"),
        ):
            section = page.locator(selector)
            section.scroll_into_view_if_needed()
            section.screenshot(path=str(output / f"guide-{size_name}-{section_name}.png"), animations="disabled")
            _overflow(page, report, f"guide-{size_name}-{section_name}")
        context.close()


def _fake_login_error(page: Page, output: Path, report: dict[str, Any], variant: str) -> None:
    def respond(route: Any) -> None:
        route.fulfill(
            status=401,
            content_type="application/json",
            body=json.dumps({"error": "Credenciales inválidas"}),
        )

    page.route("**/api/auth/login", respond)
    page.get_by_test_id("username").fill("visual-smoke")
    page.get_by_test_id("password").fill("invalid-password")
    page.get_by_test_id("login-submit").click()
    alert = page.get_by_role("alert")
    alert.wait_for(state="visible", timeout=8_000)
    report["login_error_ui"][variant] = alert.inner_text()
    _save(page, output, f"wallet-{variant}-login-error.png")
    page.unroute("**/api/auth/login", respond)


def _check_wallet(browser: Any, output: Path, report: dict[str, Any], variant: str) -> None:
    base_url = WALLETS[variant]
    for size_name, viewport in VIEWPORTS.items():
        context = browser.new_context(viewport=viewport, reduced_motion="reduce", locale="es-AR")
        page = context.new_page()
        _attach_browser_log(page, report)
        page.goto(base_url + "/", wait_until="domcontentloaded", timeout=20_000)
        page.get_by_test_id("login-submit").wait_for(state="visible")

        if size_name == "desktop":
            report["focus"][f"wallet-{variant}-login"] = _focus_visible(page)
            _fake_login_error(page, output, report, variant)

        page.get_by_test_id("username").fill(DEMO_USER)
        page.get_by_test_id("password").fill(DEMO_PASSWORD)
        page.get_by_test_id("login-submit").click()
        page.get_by_test_id("balance").wait_for(state="visible", timeout=12_000)
        _overflow(page, report, f"wallet-{variant}-{size_name}-overview")
        if size_name == "desktop":
            report["focus"][f"wallet-{variant}-dashboard"] = _focus_visible(page)
        _save(page, output, f"wallet-{variant}-{size_name}.png")

        for view_name, heading_name, label in (
            ("Transferencias", "Nueva transferencia", "transfers"),
            ("Actividad", "Actividad", "activity"),
            ("Cotizador", "Cotizador", "quotes"),
        ):
            page.get_by_role("button", name=view_name, exact=True).click()
            page.get_by_role("heading", name=heading_name, exact=True).wait_for(state="visible")
            _overflow(page, report, f"wallet-{variant}-{size_name}-{label}")
            if size_name == "desktop":
                _save(page, output, f"wallet-{variant}-{label}.png")
        context.close()


def run(output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "guide": GUIDE_URL,
        "wallets": WALLETS,
        "viewports": VIEWPORTS,
        "layouts": {},
        "focus": {},
        "login_error_ui": {},
        "console_errors": [],
        "page_errors": [],
        "screenshots": [],
        "failures": [],
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            _check_guide(browser, output, report)
            for variant in WALLETS:
                _check_wallet(browser, output, report, variant)
        finally:
            browser.close()

    report["screenshots"] = sorted(path.name for path in output.glob("*.png"))
    for label, layout in report["layouts"].items():
        if layout["horizontal_overflow"]:
            report["failures"].append(f"Desbordamiento horizontal: {label} ({layout})")
    for label, focus in report["focus"].items():
        if not focus["focus_visible"]:
            report["failures"].append(f"Foco sin indicador visible: {label} ({focus})")
    if report["page_errors"]:
        report["failures"].append("Se observaron errores JavaScript no controlados.")
    if report["console_errors"]:
        report["failures"].append("Se observaron errores de consola del navegador.")
    if any(not message for message in report["login_error_ui"].values()):
        report["failures"].append("Un error de inicio de sesión no mostró el mensaje accesible.")

    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("/state/visual"))
    arguments = parser.parse_args()
    report = run(arguments.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
