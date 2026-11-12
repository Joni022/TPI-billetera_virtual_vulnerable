"""Casos cerrados sobre datos ficticios del laboratorio local."""
from urllib.parse import parse_qs, urlencode, urlsplit

import requests
from playwright.sync_api import sync_playwright
from lab.captures import write_screenshot

PASSWORD = "Demo1234!"
PROVIDER = "http://quote-provider:8080/quote/USD"
PRIVATE = "http://private-ledger:8080/demo"


class ScenarioError(Exception):
    pass


class WalletClient:
    def __init__(self, browser, base):
        self.base = base
        self.context = browser.new_context(viewport={"width": 1280, "height": 820}, locale="es-AR")
        self.page = self.context.new_page()
        self.page.set_default_timeout(12000)

    def get(self, path):
        response = self.context.request.get(self.base + path, timeout=10000)
        if response.status >= 500:
            raise ScenarioError("Servicio no disponible; no se puede verificar el caso.")
        if response.status == 401 and path not in ('/api/csrf-token',):
            raise ScenarioError("La sesión cambió durante la prueba; resultado inconcluso.")
        return response.status, response.json()

    def post(self, path, body):
        status, value = self.get("/api/csrf-token")
        if status != 200 or not value.get("token"):
            raise ScenarioError("No se pudo preparar una sesión normal.")
        response = self.context.request.post(self.base + path, data=body,
                                             headers={"Origin": self.base, "X-CSRF-Token": value["token"]}, timeout=15000)
        if response.status >= 500:
            raise ScenarioError("Servicio no disponible; no se puede verificar el caso.")
        if response.status == 401 and path != '/api/auth/login':
            raise ScenarioError("La sesión cambió durante la prueba; resultado inconcluso.")
        return response.status, response.json()

    def login(self, username):
        status, _ = self.post("/api/auth/login", {"username": username, "password": PASSWORD})
        if status != 200:
            raise ScenarioError("No se pudo iniciar sesión con la cuenta de demostración. Restablecer datos.")

    def me(self):
        status, value = self.get("/api/me")
        if status != 200:
            raise ScenarioError("La sesión cambió durante la prueba; resultado inconcluso.")
        return value["user"]

    def screenshot(self, directory, name):
        self.page.goto(self.base, wait_until="networkidle")
        self.page.get_by_test_id("balance").wait_for()
        write_screenshot(self.page, directory, name, full_page=True)


def result(variant, observed, evidence):
    return {"outcome": ("attack_reproduced" if variant == "vulnerable" else "blocked") if observed else "unexpected",
            "evidence": evidence}


def access_control(browser, variant, base, directory):
    user = WalletClient(browser, base)
    user.login("ana")
    before = user.me()
    if before["balance_cents"] != 100000:
        raise ScenarioError("El saldo inicial cambió; restablecer ambas versiones antes del ejercicio.")
    user.screenshot(directory, "before.png")
    body = {"user_id": before["id"], "delta_cents": 5000, "reason": "Demostración control de acceso"}
    status, response = user.post("/api/admin/adjustments", body)
    after = user.me()
    expected_status, expected_balance = (200, 105000) if variant == "vulnerable" else (403, 100000)
    if status == expected_status and after["balance_cents"] != expected_balance:
        raise ScenarioError("El saldo no corresponde al efecto aislado del caso; posible interferencia manual.")
    # The legitimate administrative operation must still work.
    admin = WalletClient(browser, base)
    admin.login("admin")
    legitimate, _ = admin.post("/api/admin/adjustments", {"user_id": before["id"], "delta_cents": 100,
                                                       "reason": "Control legítimo del administrador"})
    # Return the positive-control adjustment to preserve a clear before/after comparison.
    if legitimate == 200:
        admin.post("/api/admin/adjustments", {"user_id": before["id"], "delta_cents": -100,
                                              "reason": "Reversión del control legítimo"})
    user.screenshot(directory, "after.png")
    return result(variant, status == expected_status and after["balance_cents"] == expected_balance and legitimate == 200,
                  {"summary": "Un usuario común intenta ajustar su saldo; también se verifica la operación legítima del administrador.",
                   "request": {"method": "POST", "path": "/api/admin/adjustments", "body": body, "status": status},
                   "before": before, "after": {**after, "legitimate_admin_status": legitimate, "response": response}})


def sqli(browser, variant, base, directory):
    user = WalletClient(browser, base)
    user.login("ana")
    if user.me()["balance_cents"] != 100000:
        raise ScenarioError("Estado inicial alterado. Restablecer datos.")
    admin = WalletClient(browser, base)
    admin.login("admin")
    for client, concept in ((user, "Compra propia"), (admin, "Movimiento reservado")):
        code, _ = client.post("/api/transfers", {"recipient": "bruno", "amount_cents": 100, "concept": concept})
        if code != 200:
            raise ScenarioError("No se pudieron preparar los movimientos de demostración.")
    _, before = user.get("/api/movements")
    user.page.goto(base, wait_until="networkidle")
    user.page.get_by_role("button", name="Actividad", exact=True).click()
    user.page.get_by_text("Compra propia", exact=True).wait_for(state="visible")
    write_screenshot(user.page, directory, "before.png", full_page=True)
    payload = "' OR 1=1 --"
    status, after = user.get("/api/movements?" + urlencode({"q": payload}))
    rows = after.get("movements", [])
    leaked = any(row.get("concept") == "Movimiento reservado" for row in rows)
    # Show the very same search in the real frontend for the screenshot.
    search = user.page.get_by_test_id("movements-search")
    with user.page.expect_response(lambda response: response.request.method == "GET"
                                   and urlsplit(response.url).path == "/api/movements"
                                   and parse_qs(urlsplit(response.url).query).get("q") == [payload]):
        search.fill(payload)
    user.page.wait_for_function("""(concepts) => {
        const rows = [...document.querySelectorAll('[data-testid=movements-list] .movement-row')];
        return rows.length === concepts.length && concepts.every((concept, index) =>
          rows[index].querySelector('.movement-concept')?.textContent === concept);
    }""", arg=[row.get("concept", "") for row in rows])
    write_screenshot(user.page, directory, "after.png", full_page=True)
    return result(variant, status == 200 and (leaked if variant == "vulnerable" else not leaked and not rows),
                  {"summary": "La búsqueda intenta cambiar la condición de autorización y obtener un movimiento entre otros usuarios.",
                   "request": {"method": "GET", "path": "/api/movements", "query": payload, "status": status},
                   "before": before, "after": {"movements": rows, "foreign_movement_exposed": leaked}})


def authentication(browser, variant, base, directory):
    user = WalletClient(browser, base)
    user.page.goto(base)
    user.page.get_by_test_id("login-submit").wait_for()
    write_screenshot(user.page, directory, "before.png", full_page=True)
    first_status, existing = user.post("/api/auth/login", {"username": "ana", "password": "Incorrecta123!"})
    unknown_status, unknown = user.post("/api/auth/login", {"username": "noexiste", "password": "Incorrecta123!"})
    statuses = []
    for _ in range(6):
        status, _ = user.post("/api/auth/login", {"username": "ana", "password": "Incorrecta123!"})
        statuses.append(status)
    user.page.get_by_test_id("username").fill("ana")
    user.page.get_by_test_id("password").fill("Incorrecta123!")
    user.page.get_by_test_id("login-submit").click()
    user.page.get_by_role("alert").wait_for(state="visible")
    write_screenshot(user.page, directory, "after.png", full_page=True)
    uniform = existing.get("error") == unknown.get("error")
    limited = 429 in statuses
    expected = (not uniform and not limited) if variant == "vulnerable" else (uniform and limited)
    return result(variant, first_status == 401 and unknown_status == 401 and expected,
                  {"summary": "Se comparan errores de login y se realizan intentos acotados sobre una cuenta ficticia.",
                   "request": {"method": "POST", "path": "/api/auth/login", "body": {"username": "ana / noexiste", "password": "[oculta]"}, "status": statuses},
                   "before": {"existing_account_message": existing.get("error"), "unknown_account_message": unknown.get("error")},
                   "after": {"attempt_statuses": statuses, "messages_uniform": uniform, "rate_limit_observed": limited}})


def ssrf(browser, variant, base, directory):
    user = WalletClient(browser, base)
    user.login("ana")
    user.page.goto(base, wait_until="networkidle")
    user.page.get_by_role("button", name="Cotizador", exact=True).click()
    user.page.get_by_label("URL del proveedor").wait_for(state="visible")
    write_screenshot(user.page, directory, "before.png", full_page=True)
    session = requests.Session()
    session.trust_env = False
    counter_before = session.get("http://private-ledger:8080/stats", timeout=3).json()["/demo"]
    good_status, good_result = user.post("/api/quotes/import", {"url": PROVIDER})
    user.page.get_by_label("URL del proveedor").fill(PRIVATE)
    with user.page.expect_response(lambda response: response.request.method == 'POST' and response.url.endswith('/api/quotes/import')) as pending:
        user.page.get_by_role("button", name="Consultar", exact=True).click()
    api_response = pending.value
    status, response = api_response.status, api_response.json()
    if status >= 500:
        raise ScenarioError("El proveedor no respondió; no es evidencia de bloqueo.")
    counter_after = session.get("http://private-ledger:8080/stats", timeout=3).json()["/demo"]
    calls = counter_after - counter_before
    leaked = "DATO INTERNO FICTICIO" in str(response)
    if calls not in (0, 1):
        raise ScenarioError("Se detectaron llamadas concurrentes al servicio interno.")
    if status == 200 and leaked:
        user.page.get_by_text("DATO INTERNO FICTICIO", exact=False).wait_for(state="visible")
    elif status in (400, 403):
        user.page.get_by_role("alert").wait_for(state="visible")
    else:
        user.page.get_by_role("button", name="Consultar", exact=True).wait_for(state="visible")
    write_screenshot(user.page, directory, "after.png", full_page=True)
    expected = (status == 200 and leaked and calls == 1) if variant == "vulnerable" else (status in (400, 403) and not leaked and calls == 0)
    return result(variant, good_status == 200 and good_result.get("result", {}).get("currency") == "USD" and expected,
                  {"summary": "El proveedor legítimo funciona; se intenta consultar un servicio interno ficticio desde el servidor.",
                   "request": {"method": "POST", "path": "/api/quotes/import", "body": {"url": PRIVATE}, "status": status},
                   "before": {"internal_requests": counter_before, "legitimate_provider_status": good_status},
                   "after": {"internal_requests": counter_after, "response": response, "internal_data_exposed": leaked}})


def run_api_case(case_id, variant, base, directory):
    functions = {"access-control": access_control, "sqli": sqli, "authentication": authentication, "ssrf": ssrf}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            return functions[case_id](browser, variant, base, directory)
        finally:
            browser.close()
