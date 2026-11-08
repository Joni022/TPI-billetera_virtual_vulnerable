import json
import sys
import threading
from pathlib import Path

from lab.runner import CASES, VARIANTS


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
    (output / "worker-result.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
