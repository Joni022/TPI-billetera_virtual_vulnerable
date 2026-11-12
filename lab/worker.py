import json
import sys
import threading
from pathlib import Path

from lab.runner import CASES, VARIANTS


CAPTURE_DESCRIPTIONS = {
    "access-control": ("Saldo de Ana antes del intento de ajuste.",
                       "Saldo de Ana después del intento; si fue rechazado, permanece igual."),
    "csrf": ("Saldo y actividad de Ana antes del envío del formulario.",
             "Saldo y actividad de Ana después del envío; si fue rechazado, permanecen iguales."),
    "xss": ("Billetera de Bruno antes de recibir el concepto de prueba.",
            "Actividad de Bruno después de recibir el concepto; muestra el marcador o el texto literal."),
    "sqli": ("Actividad de Ana antes de la búsqueda de prueba.",
             "Resultado de la búsqueda de prueba en Actividad."),
    "authentication": ("Formulario de acceso antes de los intentos.",
                       "Respuesta visible del formulario después de los intentos."),
    "ssrf": ("Cotizador antes de consultar el servicio interno ficticio.",
             "Resultado visible de la consulta al servicio interno ficticio."),
}


def main():
    case_id, variant, base_url, directory = sys.argv[1:]
    if case_id not in CASES or variant not in VARIANTS or base_url != ("http://localhost:5000" if variant == "vulnerable" else "http://localhost:5001"):
        raise ValueError("Configuración de ejecución inválida")
    output = Path(directory)
    try:
        if case_id in ("csrf", "xss"):
            from tests_browser.scenarios import run_browser_case
            result = run_browser_case(case_id, variant, base_url, "http://localhost:5003", output, threading.Event())
        else:
            from lab.api_cases import run_api_case
            result = run_api_case(case_id, variant, base_url, output)
    except Exception as error:
        # Deliberately do not serialize tracebacks, URLs, browser cookies or credentials.
        message = "No se pudo completar la prueba en el navegador. Comprobar servicios y restablecer datos."
        from lab.api_cases import ScenarioError
        if isinstance(error, ScenarioError):
            message = str(error)
        result = {"outcome": "inconclusive", "evidence": {"summary": message, "error_type": type(error).__name__}}
    descriptions = CAPTURE_DESCRIPTIONS[case_id]
    # Only expose completed captures, not a partial file left behind by an error.
    names = result.get("evidence", {}).get("screenshots")
    if names is None and result["outcome"] != "inconclusive":
        names = [name for name in ("before.png", "after.png") if (output / name).is_file()]
    result["evidence"]["captures"] = [
        {"filename": name, "phase": phase, "label": label, "description": description}
        for name, phase, label, description in (
            ("before.png", "before", "Antes", descriptions[0]),
            ("after.png", "after", "Después", descriptions[1]),
        ) if name in (names or [])
    ]
    (output / "worker-result.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
