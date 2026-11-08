import { useCallback, useEffect, useRef, useState } from "react";
import {
  getLabRun,
  getLabRuns,
  getLabStatus,
  HttpError,
  labPost,
} from "../shared/api";
import type { LabResult, LabRun, LabStatus, Variant } from "../shared/types";

type CaseId = "access-control" | "csrf" | "xss" | "sqli" | "authentication" | "ssrf";

type Exercise = {
  id: CaseId;
  title: string;
  short: string;
  goal: string;
  prerequisites: string[];
  steps: string[];
  request: string;
  vulnerable: string;
  corrected: string;
  fix: string;
  payload?: string;
};

const XSS_PAYLOAD =
  '<img src=x onerror="' +
  "document.body.insertAdjacentHTML('afterbegin','<div data-testid=&quot;xss-marker&quot; style=&quot;color:red;font-weight:bold&quot;>XSS ejecutado</div>');" +
  'this.remove()">';
const SQLI_PAYLOAD = "' OR 1=1 --";

const EXERCISES: Exercise[] = [
  {
    id: "access-control",
    title: "Autorización y rol de administrador",
    short: "Acceso a ajustes",
    goal: "Comprobar que la API valida el rol en cada operación privilegiada.",
    prerequisites: ["Ingresá en la billetera vulnerable con ana.", "Anotá su saldo antes de empezar: 100000 centavos."],
    steps: [
      "Abrí las herramientas del navegador en la página de la billetera y consultá /api/me para obtener tu id ficticio.",
      "Enviá un POST a /api/admin/adjustments para acreditar 5000 centavos en tu propia cuenta.",
      "En vulnerable, compará el saldo de ana: debe pasar de 100000 a 105000 centavos.",
      "Repetí la misma solicitud en corregida: debe rechazarse y conservar el saldo.",
      "Como control positivo, ingresá como admin y comprobá que puede aplicar y revertir un ajuste pequeño.",
    ],
    request: 'POST /api/admin/adjustments\n{ "user_id": <id de ana>, "delta_cents": 5000, "reason": "Demostración control de acceso" }',
    vulnerable: "Ana puede acreditar $50 ficticios a su cuenta: 100000 → 105000 centavos.",
    corrected: "El servidor rechaza el ajuste y conserva el saldo; un administrador sigue pudiendo ajustar.",
    fix: "Validar autorización en el servidor en cada ruta sensible; el rol del cliente no concede permisos.",
    payload:
      'const me = await (await fetch("/api/me")).json();\nconst token = (await (await fetch("/api/csrf-token")).json()).token;\nawait fetch("/api/admin/adjustments", { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": token }, body: JSON.stringify({ user_id: me.user.id, delta_cents: 5000, reason: "Demostración control de acceso" }) });',
  },
  {
    id: "csrf",
    title: "Solicitud entre sitios (CSRF)",
    short: "Transferencia forzada",
    goal: "Ver si una página en otro origen puede iniciar una transferencia con la sesión abierta.",
    prerequisites: ["Ingresá normalmente a la billetera que vas a probar.", "Usá la misma ventana del navegador para abrir la página atacante local."],
    steps: [
      "Elegí la variante vulnerable y dejá abierta la billetera con ana.",
      "Abrí la página atacante local en otra pestaña y seleccioná Vulnerable.",
      "La página envía un formulario real con una transferencia ficticia de $25 a bruno.",
      "Volvé a la billetera y revisá el saldo y la actividad.",
      "Repetí el ejercicio con la variante corregida.",
    ],
    request: "POST /api/transfers\nrecipient=bruno · amount_cents=2500 · concept=Demostración CSRF",
    vulnerable: "La transferencia aparece en la actividad y modifica los saldos ficticios.",
    corrected: "La solicitud sin token CSRF se rechaza y no modifica los saldos.",
    fix: "Exigir un token anti-CSRF para toda mutación y validar el origen según la política del servidor.",
  },
  {
    id: "xss",
    title: "XSS persistente en el concepto",
    short: "Contenido almacenado",
    goal: "Observar cómo un concepto guardado puede ejecutarse cuando otro usuario abre la actividad.",
    prerequisites: ["Ingresá en la billetera con ana.", "Usá el concepto de prueba que aparece abajo; no uses datos personales."],
    steps: [
      "En Transferencias, enviá $1 a bruno y pegá el payload como concepto.",
      "Cerrá sesión de ana e ingresá como bruno, en la misma variante.",
      "Abrí Actividad de bruno y buscá la transferencia entrante.",
      "En la variante vulnerable, aparece un marcador visible “XSS ejecutado”.",
      "En la variante corregida, el texto del payload se muestra literal y no aparece el marcador.",
    ],
    request: "POST /api/transfers\nconcept=<payload HTML de prueba>",
    vulnerable: "El navegador crea un marcador HTML visible al renderizar el concepto almacenado.",
    corrected: "React representa el concepto como texto; no crea el elemento ni muestra el marcador.",
    fix: "Codificar el contenido al renderizarlo; evitar sinks HTML sin sanitización y aplicar CSP como defensa adicional.",
    payload: XSS_PAYLOAD,
  },
  {
    id: "sqli",
    title: "Inyección SQL en la búsqueda",
    short: "Historial y búsqueda",
    goal: "Comparar la búsqueda de actividad ante una condición que amplía la consulta.",
    prerequisites: ["Restablecé ambas variantes e iniciá sesión con ana.", "Creá un movimiento de ana a bruno y otro de admin a bruno; volvé a ingresar con ana.", "Este ejercicio sólo consulta movimientos."],
    steps: [
      "Abrí Actividad en la billetera.",
      "Pegá el payload en el campo de búsqueda y enviá la consulta.",
      "Observá si aparecen movimientos que no corresponden a ana o si el servidor devuelve un error SQL.",
      "Repetí la búsqueda en la variante corregida y compará las filas.",
    ],
    request: "GET /api/movements?q=<payload>",
    vulnerable: "La condición altera la consulta y puede ampliar los resultados.",
    corrected: "El texto se trata como un valor; no aparecen filas adicionales.",
    fix: "Usar consultas parametrizadas y limitar cada resultado a la cuenta autenticada.",
    payload: SQLI_PAYLOAD,
  },
  {
    id: "authentication",
    title: "Enumeración y limitación de intentos",
    short: "Acceso a cuentas",
    goal: "Comparar los mensajes de login y la respuesta ante intentos repetidos.",
    prerequisites: ["Usá nombres de usuario y contraseñas ficticios.", "Restablecé el laboratorio antes de empezar para limpiar el estado de intentos."],
    steps: [
      "En la pantalla de login, probá un usuario inexistente con una contraseña cualquiera.",
      "Probá ana con una contraseña incorrecta y compará los mensajes.",
      "Repetí varios intentos con la misma cuenta y anotá cuándo se aplica el límite.",
      "Repetí en la variante corregida.",
    ],
    request: 'POST /api/auth/login\n{ "username": "ana o usuario-inexistente", "password": "incorrecta" }',
    vulnerable: "Puede diferenciar una cuenta inexistente y aceptar intentos repetidos sin el límite esperado.",
    corrected: "Devuelve un rechazo genérico y limita intentos reiterados.",
    fix: "Unificar mensajes de autenticación y aplicar limitación de intentos en servidor, también por origen y cuenta.",
  },
  {
    id: "ssrf",
    title: "SSRF al importar una cotización",
    short: "Proveedor externo",
    goal: "Verificar que el servidor sólo consulte el proveedor de cotizaciones permitido.",
    prerequisites: ["Abrí Cotizador en la billetera.", "Las direcciones del ejercicio sólo existen dentro de la red Docker del laboratorio."],
    steps: [
      "Consultá primero el proveedor permitido: http://quote-provider:8080/quote/USD.",
      "Probá después la URL del servicio interno ficticio: http://private-ledger:8080/demo.",
      "Compará la respuesta de ambas variantes y la evidencia del test automático.",
    ],
    request: 'POST /api/quotes/import\n{ "url": "http://private-ledger:8080/demo" }',
    vulnerable: "El servidor puede devolver información del fixture interno ficticio.",
    corrected: "El servidor rechaza el destino interno y no consulta el fixture.",
    fix: "Construir el destino desde una allowlist exacta del proveedor simulado; validar ruta, desactivar redirecciones y limitar tiempo/tamaño. Mantener la excepción del fixture interno sólo en la variante de laboratorio aislada.",
    payload: "http://private-ledger:8080/demo",
  },
];

function formatRunStatus(status: string): string {
  const normalized = status.toLowerCase();
  if (normalized === "queued" || normalized === "pending") return "En cola";
  if (normalized === "running" || normalized === "active") return "En curso";
  if (normalized === "completed" || normalized === "done") return "Finalizado";
  if (normalized === "cancelled" || normalized === "canceled") return "Cancelado";
  if (normalized === "timeout" || normalized === "timed_out") return "Tiempo agotado";
  if (normalized === "failed" || normalized === "error") return "Error";
  return status;
}

function expectedForVariant(result: LabResult): boolean {
  return result.variant === "vulnerable"
    ? result.outcome === "attack_reproduced"
    : result.outcome === "blocked";
}

function displayOutcome(result: LabResult): string {
  if (result.outcome === "inconclusive") return "Inconcluso";
  if (result.outcome === "unexpected") return "Resultado inesperado";
  if (expectedForVariant(result)) {
    return result.variant === "vulnerable" ? "Exposición reproducida" : "Solicitud bloqueada";
  }
  return result.variant === "secure" ? "Ataque inesperado" : "Se esperaba reproducir la falla";
}

function errorText(error: unknown): string {
  if (error instanceof HttpError) {
    if (error.status === 409) {
      if (error.message.toLowerCase().includes("restablecer")) {
        return "Restablecé ambas billeteras antes de iniciar el siguiente ejercicio.";
      }
      return "Ya hay una ejecución o un restablecimiento en curso. Esperá a que termine.";
    }
    if (error.status === 503) {
      const payload = error.payload as { status?: string; variants?: Record<string, { ok?: boolean; error?: string }> };
      if (payload?.status === "failed") return "No se pudo restablecer ninguna billetera. Revisá los servicios y volvé a intentarlo.";
      if (payload?.status === "partial") {
        const failed = Object.entries(payload.variants ?? {}).filter(([, value]) => value.ok !== true).map(([name]) => name);
        return "Restablecimiento parcial" + (failed.length ? " en " + failed.join(" y ") : "") + ". No ejecutes más casos hasta restablecer ambas.";
      }
      return "Una de las variantes no pudo restablecerse. El estado quedó parcial; restablecé ambas antes de repetir.";
    }
  }
  if (error instanceof Error) return error.message;
  return "No se pudo contactar la guía local. Intentá de nuevo.";
}

export default function GuideApp() {
  const [status, setStatus] = useState<LabStatus | null>(null);
  const [runs, setRuns] = useState<LabRun[]>([]);
  const [selectedCase, setSelectedCase] = useState<CaseId>("access-control");
  const [activeRun, setActiveRun] = useState<LabRun | null>(null);
  const [busyAction, setBusyAction] = useState<"reset" | "run" | "cancel" | null>(null);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [message, setMessage] = useState("");
  const [copyNotice, setCopyNotice] = useState("");
  const [confirm, setConfirm] = useState<"reset" | "case" | "all" | null>(null);
  const [pendingCase, setPendingCase] = useState<CaseId>("access-control");
  const refreshLock = useRef(false);

  const refresh = useCallback(async () => {
    if (refreshLock.current) return;
    refreshLock.current = true;
    try {
      const [nextStatus, nextRuns] = await Promise.all([getLabStatus(), getLabRuns()]);
      setStatus(nextStatus);
      setRuns(nextRuns.runs);
      if (nextStatus.active_run_id) {
        const current = await getLabRun(nextStatus.active_run_id);
        setActiveRun(current);
      } else {
        setActiveRun(null);
      }
      setLoadError("");
    } catch (loadError) {
      setLoadError(errorText(loadError));
    } finally {
      refreshLock.current = false;
    }
  }, []);

  useEffect(() => {
    void refresh();
    const interval = window.setInterval(() => void refresh(), 1800);
    return () => window.clearInterval(interval);
  }, [refresh]);

  async function resetBoth() {
    setBusyAction("reset");
    setError("");
    setMessage("");
    try {
      const result = await labPost<{ status: string }>("/lab/api/reset", {});
      if (result.data.status === "partial") {
        setError("El restablecimiento quedó parcial. No ejecutes ejercicios hasta restablecer ambas variantes.");
      } else {
        setMessage("Datos restablecidos en ambas billeteras. Las sesiones se cerraron; ingresá de nuevo con una cuenta demo. La evidencia anterior se conserva.");
      }
      await refresh();
    } catch (resetError) {
      await refresh();
      setError(errorText(resetError));
    } finally {
      setBusyAction(null);
      setConfirm(null);
    }
  }

  async function startRun(caseId: CaseId | "all") {
    setBusyAction("run");
    setError("");
    setMessage("");
    try {
      const result = await labPost<{ id: string; status: string }>("/lab/api/runs", {
        case_id: caseId,
        reset_first: caseId === "all",
      });
      setActiveRun({
        id: result.data.id,
        case_id: caseId,
        status: result.data.status,
        results: [],
      });
      setMessage(
        caseId === "all"
          ? "El lote ejecutará 12 verificaciones en secuencia y restablecerá las dos billeteras antes de cada ejercicio."
          : "La prueba usa las billeteras visibles y deja los cambios para que puedas revisarlos.",
      );
      await refresh();
    } catch (runError) {
      await refresh();
      setError(errorText(runError));
    } finally {
      setBusyAction(null);
      setConfirm(null);
    }
  }

  async function cancelRun() {
    if (!activeRun) return;
    setBusyAction("cancel");
    setError("");
    try {
      await labPost<{ status: string }>("/lab/api/runs/" + encodeURIComponent(activeRun.id) + "/cancel", {});
      setMessage("Se solicitó cancelar. Los cambios que ya ocurrieron y la evidencia parcial quedan visibles.");
      await refresh();
    } catch (cancelError) {
      setError(errorText(cancelError));
    } finally {
      setBusyAction(null);
    }
  }

  async function copyText(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopyNotice("Copiado.");
      window.setTimeout(() => setCopyNotice(""), 1800);
    } catch {
      setCopyNotice("No se pudo copiar; seleccioná el texto manualmente.");
      window.setTimeout(() => setCopyNotice(""), 3000);
    }
  }

  const currentExercise = EXERCISES.find((exercise) => exercise.id === selectedCase) ?? EXERCISES[0];
  const active = Boolean(status?.active || (activeRun && ["running", "queued", "pending"].includes(activeRun.status.toLowerCase())));

  return (
    <div className="guide-shell">
      <header className="guide-header">
        <div className="guide-header-inner">
          <span className="brand-lockup" aria-label="Umbral">
            <span className="brand-symbol" aria-hidden="true">U</span>
            <span><strong>umbral</strong><small>Guía de seguridad</small></span>
          </span>
          <div className="guide-header-actions">
            <span className={"guide-live " + (active ? "guide-live-active" : "")}>
              <span aria-hidden="true" /> {active ? "Prueba en curso" : "Laboratorio local"}
            </span>
            <a className="button button-secondary" href={status?.variants.vulnerable.url ?? "http://localhost:5000/"} target="_blank" rel="noreferrer">Abrir billetera</a>
          </div>
        </div>
      </header>

      <main className="guide-main">
        <section className="guide-intro">
          <div>
            <p className="context-label">Práctica guiada · datos ficticios</p>
            <h1>Seguridad, vista desde adentro.</h1>
            <p>Seis ejercicios manuales y automáticos para observar el mismo flujo en la variante vulnerable y la corregida.</p>
          </div>
          <div className="guide-summary" aria-live="polite">
            <div><strong>{status?.needs_reset ? "Requiere reset" : active ? "En ejecución" : "Lista para probar"}</strong><span>Estado de las billeteras</span></div>
            <div><strong>{runs.length} / 10</strong><span>Informes recientes</span></div>
          </div>
        </section>

        {(error || loadError) && <p className="guide-alert guide-alert-error" role="alert">{error || loadError}</p>}
        {message && <p className="guide-alert guide-alert-info" role="status">{message}</p>}

        <section className="demo-access" aria-labelledby="demo-access-title">
          <div className="demo-access-heading">
            <div>
              <p className="context-label">Acceso de práctica</p>
              <h2 id="demo-access-title">Cuentas ficticias</h2>
            </div>
            <p>Copiá una credencial e ingresá normalmente en cada billetera.</p>
          </div>
          <div className="credential-list">
            {(status?.credentials ?? []).map((credential) => (
              <div className="credential-row" key={credential.username}>
                <span className="credential-user"><strong>{credential.username}</strong><small>{credential.role}</small></span>
                <code>{credential.password}</code>
                <button type="button" className="button button-quiet" onClick={() => void copyText(credential.password)}>Copiar clave</button>
              </div>
            ))}
            {!status?.credentials?.length && <p className="body-muted">Cargando cuentas demo…</p>}
          </div>
        </section>

        <section className="environment-section" aria-labelledby="environment-title">
          <div className="section-title-row">
            <div><h2 id="environment-title">Dos variantes, los mismos datos iniciales</h2><p>Los ejercicios automáticos usan estas billeteras visibles, no copias ocultas.</p></div>
            <button
              type="button"
              className="button button-secondary"
              disabled={active || busyAction !== null}
              onClick={() => setConfirm("reset")}
            >
              {busyAction === "reset" ? "Restableciendo…" : "Restablecer ambas versiones"}
            </button>
          </div>
          <div className="environment-grid">
            <EnvironmentCard
              variant="vulnerable"
              url={status?.variants.vulnerable.url ?? "http://localhost:5000/"}
            />
            <EnvironmentCard
              variant="secure"
              url={status?.variants.secure.url ?? "http://localhost:5001/"}
            />
          </div>
          {status?.needs_reset && (
            <p className="reset-reminder" role="status">
              Para un resultado independiente, restablecé ambas variantes antes del siguiente ejercicio. El restablecimiento invalida las sesiones.
            </p>
          )}
        </section>

        <section className="practice-section" aria-labelledby="practice-title">
          <div className="practice-heading">
            <div>
              <p className="context-label">Seis vulnerabilidades</p>
              <h2 id="practice-title">Elegí un ejercicio</h2>
              <p>Seguí los pasos manuales o ejecutá la verificación sobre ambas variantes.</p>
            </div>
            <button
              type="button"
              className="button button-primary"
              disabled={active || busyAction !== null}
              onClick={() => setConfirm("all")}
            >
              Ejecutar los seis · 12 verificaciones
            </button>
          </div>
          {active && (
            <div className="active-run-banner" aria-live="polite">
              <div>
                <strong>{activeRun ? "Ejercicio en curso" : status?.active ? "Restablecimiento en curso" : "Preparando ejecución"}</strong>
                <span>{activeRun?.current ? currentCaseName(activeRun.current.case_id) + " · " + variantLabel(activeRun.current.variant) : "Las billeteras están reservadas para el laboratorio."}</span>
              </div>
              <button type="button" className="button button-quiet" onClick={() => void cancelRun()} disabled={busyAction === "cancel"}>
                {busyAction === "cancel" ? "Cancelando…" : "Cancelar"}
              </button>
            </div>
          )}
          <div className="exercise-layout">
            <nav className="exercise-nav" aria-label="Ejercicios">
              {EXERCISES.map((exercise, index) => (
                <button
                  type="button"
                  key={exercise.id}
                  className={"exercise-nav-item " + (selectedCase === exercise.id ? "exercise-nav-active" : "")}
                  aria-current={selectedCase === exercise.id ? "step" : undefined}
                  onClick={() => setSelectedCase(exercise.id)}
                >
                  <span className="exercise-number">{String(index + 1).padStart(2, "0")}</span>
                  <span><strong>{exercise.short}</strong><small>{exercise.title}</small></span>
                </button>
              ))}
            </nav>
            <article className="exercise-detail" aria-labelledby="selected-exercise-title">
              <div className="exercise-title-row">
                <div>
                  <p className="context-label">Ejercicio {String(EXERCISES.findIndex((item) => item.id === currentExercise.id) + 1).padStart(2, "0")}</p>
                  <h3 id="selected-exercise-title">{currentExercise.title}</h3>
                  <p>{currentExercise.goal}</p>
                </div>
                <button
                  type="button"
                  className="button button-primary"
                  disabled={active || busyAction !== null || status?.needs_reset}
                  onClick={() => { setPendingCase(currentExercise.id); setConfirm("case"); }}
                  title={status?.needs_reset ? "Restablecé ambas billeteras antes de ejecutar otro ejercicio." : undefined}
                >
                  {busyAction === "run" ? "Iniciando…" : "Ejecutar en ambas"}
                </button>
              </div>
              {status?.needs_reset && (
                <p className="guide-alert guide-alert-warning" role="status">
                  Esta prueba necesita datos limpios. Restablecé ambas billeteras; después iniciá sesión normalmente y ejecutala.
                </p>
              )}
              <div className="manual-grid">
                <section className="manual-panel">
                  <h4>Ejercicio manual</h4>
                  <h5>Antes de empezar</h5>
                  <ul>{currentExercise.prerequisites.map((item) => <li key={item}>{item}</li>)}</ul>
                  <h5>Pasos</h5>
                  <ol>{currentExercise.steps.map((item) => <li key={item}>{item}</li>)}</ol>
                  <div className="manual-request">
                    <div className="manual-request-heading"><strong>Petición a observar</strong><button className="text-button" type="button" onClick={() => void copyText(currentExercise.request)}>Copiar</button></div>
                    <pre>{currentExercise.request}</pre>
                  </div>
                  {currentExercise.payload && (
                    <div className="manual-payload">
                      <div className="manual-request-heading"><strong>{currentExercise.id === "xss" ? "Concepto de prueba" : currentExercise.id === "ssrf" ? "URL de servicio interno simulado" : currentExercise.id === "sqli" ? "Búsqueda de prueba" : "Solicitud de ejemplo"}</strong><button className="text-button" type="button" onClick={() => void copyText(currentExercise.payload ?? "")}>Copiar</button></div>
                      <pre>{currentExercise.payload}</pre>
                    </div>
                  )}
                  {currentExercise.id === "csrf" && (
                    <div className="attacker-links">
                      <a className="button button-secondary" href="http://localhost:5003/?variant=vulnerable" target="_blank" rel="noreferrer">Abrir atacante · vulnerable</a>
                      <a className="button button-secondary" href="http://localhost:5003/?variant=secure" target="_blank" rel="noreferrer">Abrir atacante · corregida</a>
                    </div>
                  )}
                </section>
                <section className="manual-panel manual-observation">
                  <h4>Qué observar</h4>
                  <div className="expected-row expected-vulnerable">
                    <span className="expected-label">Vulnerable</span>
                    <p>{currentExercise.vulnerable}</p>
                  </div>
                  <div className="expected-row expected-secure">
                    <span className="expected-label">Corregida</span>
                    <p>{currentExercise.corrected}</p>
                  </div>
                  <div className="fix-note">
                    <strong>Corrección a revisar</strong>
                    <p>{currentExercise.fix}</p>
                  </div>
                  <p className="manual-disclaimer">Las pruebas manuales cambian datos ficticios de la billetera. Usá el botón de restablecimiento antes de empezar otro caso.</p>
                </section>
              </div>
            </article>
          </div>
        </section>

        <section className="results-section" aria-labelledby="results-title">
          <div className="section-title-row">
            <div><h2 id="results-title">Resultado y evidencia</h2><p>Las solicitudes, saldos y capturas provienen de las ejecuciones reales.</p></div>
          </div>
          {activeRun && <RunPanel run={activeRun} />}
          {!activeRun && runs.length === 0 && <p className="empty-guide">Todavía no hay ejecuciones automáticas.</p>}
          {!activeRun && runs.length > 0 && (
            <div className="run-history">
              {runs.slice(0, 10).map((run, index) => <RunPanel key={run.id} run={run} compact={index > 0} />)}
            </div>
          )}
        </section>
        <p className="guide-footnote">Umbral es un laboratorio local. No uses credenciales, datos ni servicios reales. La ejecución automática es headless: vas a ver el progreso y la evidencia, no una ventana automatizada del navegador.</p>
      </main>

      {copyNotice && <div className="copy-notice" role="status">{copyNotice}</div>}
      {confirm && (
        <ConfirmDialog
          kind={confirm}
          exercise={confirm === "case" ? EXERCISES.find((item) => item.id === pendingCase) : undefined}
          busy={busyAction !== null}
          onClose={() => setConfirm(null)}
          onConfirm={() => {
            if (confirm === "reset") void resetBoth();
            else if (confirm === "all") void startRun("all");
            else void startRun(pendingCase);
          }}
        />
      )}
    </div>
  );
}

function EnvironmentCard({ variant, url }: { variant: Variant; url: string }) {
  const vulnerable = variant === "vulnerable";
  return (
    <article className="environment-card">
      <div className="environment-card-top">
        <span className={"environment-label " + (vulnerable ? "environment-label-vulnerable" : "environment-label-secure")}>
          {vulnerable ? "Vulnerable" : "Corregida"}
        </span>
        <span className="environment-port">{vulnerable ? ":5000" : ":5001"}</span>
      </div>
      <p>{vulnerable ? "Permite reproducir los fallos del ejercicio." : "Aplica los controles de seguridad esperados."}</p>
      <a href={url} target="_blank" rel="noreferrer">Abrir billetera <span aria-hidden="true">↗</span></a>
    </article>
  );
}

function ConfirmDialog({
  kind,
  exercise,
  busy,
  onClose,
  onConfirm,
}: {
  kind: "reset" | "case" | "all";
  exercise?: Exercise;
  busy: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (!dialog.open) dialog.showModal();
    return () => {
      if (dialog.open) dialog.close();
    };
  }, []);

  const title = kind === "reset"
    ? "Restablecer ambas billeteras"
    : kind === "all"
      ? "Ejecutar los seis ejercicios"
      : "Ejecutar en ambas variantes";
  const body = kind === "reset"
    ? "Se borrarán los movimientos y ajustes ficticios, se restaurarán los datos iniciales y se invalidarán las sesiones de ambas billeteras. Los informes y capturas anteriores se conservan."
    : kind === "all"
      ? "El lote ejecuta 12 verificaciones en secuencia y restablece ambas billeteras antes de cada ejercicio. Las sesiones humanas no se preservan; los informes y capturas de cada caso quedan en la guía."
    : "Se ejecuta este caso sobre las dos billeteras visibles. Los cambios ficticios quedan para compararlos; la evidencia se conserva aunque luego restablezcas los datos.";

  return (
    <dialog className="confirm-dialog" ref={dialogRef} aria-labelledby="confirm-dialog-title" aria-describedby="confirm-dialog-body" onCancel={(event) => { event.preventDefault(); onClose(); }}>
      <div className="confirm-content">
        <p className="context-label">Confirmación</p>
        <h2 id="confirm-dialog-title">{title}</h2>
        <p id="confirm-dialog-body">{body}</p>
        {exercise && <p className="confirm-case-name">{exercise.title}</p>}
        <div className="confirm-actions">
          <button className="button button-quiet" type="button" onClick={onClose} disabled={busy}>Cancelar</button>
          <button className="button button-primary" type="button" onClick={onConfirm} disabled={busy}>
            {busy ? "Un momento…" : kind === "reset" ? "Restablecer ambas" : kind === "all" ? "Ejecutar el lote" : "Ejecutar en ambas"}
          </button>
        </div>
      </div>
    </dialog>
  );
}

function currentCaseName(id: string): string {
  return EXERCISES.find((exercise) => exercise.id === id)?.short ?? id;
}

function variantLabel(variant: Variant): string {
  return variant === "vulnerable" ? "Vulnerable" : "Corregida";
}

function RunPanel({ run, compact = false }: { run: LabRun; compact?: boolean }) {
  const [expanded, setExpanded] = useState(!compact);
  const isActive = ["running", "queued", "pending"].includes(run.status.toLowerCase());
  const expectedCount = run.case_id === "all" ? 12 : 2;
  const allExpected = run.status.toLowerCase() === "completed"
    && run.results.length === expectedCount
    && run.results.every(expectedForVariant);
  return (
    <article className={"run-panel " + (compact ? "run-panel-compact" : "")}>
      <div className="run-panel-heading">
        <div>
          <span className={"run-status-chip " + (isActive ? "run-status-active" : allExpected ? "run-status-complete" : "run-status-neutral")}>
            {isActive ? "En curso" : formatRunStatus(run.status)}
          </span>
          <h3>{run.case_id === "all" ? "Lote: seis ejercicios" : currentCaseName(run.case_id)}</h3>
          <p>{run.id} · {run.results.length} resultado(s){allExpected ? " · ambos comportamientos observados" : ""}</p>
        </div>
        {compact && <button className="text-button" type="button" onClick={() => setExpanded((value) => !value)}>{expanded ? "Ocultar" : "Ver evidencia"}</button>}
      </div>
      {run.current && <p className="run-current" aria-live="polite">Ahora: {currentCaseName(run.current.case_id)} · {variantLabel(run.current.variant)}</p>}
      {run.error && <p className="guide-alert guide-alert-error" role="status">{run.error}</p>}
      {expanded && (
        <div className="run-results">
          {run.results.map((result, index) => (
            <ResultEvidence result={result} key={result.case_id + result.variant + index} />
          ))}
          {!run.results.length && isActive && <p className="run-waiting" role="status">Esperando la primera evidencia del navegador…</p>}
        </div>
      )}
    </article>
  );
}

function ResultEvidence({ result }: { result: LabResult }) {
  const expected = expectedForVariant(result);
  const tone = result.outcome === "inconclusive" ? "outcome-inconclusive" : result.outcome === "unexpected" || !expected ? "outcome-error" : result.variant === "vulnerable" ? "outcome-exposure" : "outcome-blocked";
  return (
    <section className="result-evidence">
      <div className="result-evidence-heading">
        <div>
          <span className="result-case-name">{currentCaseName(result.case_id)}</span>
          <strong>{variantLabel(result.variant)}</strong>
        </div>
        <span className={"outcome-chip " + tone}>{displayOutcome(result)}</span>
      </div>
      <p className="evidence-summary">{result.evidence.summary}</p>
      <div className="evidence-grid">
        {result.evidence.before !== undefined && <EvidenceBlock title="Antes" value={result.evidence.before} />}
        {result.evidence.request !== undefined && <EvidenceBlock title="Solicitud y respuesta" value={result.evidence.request} />}
        {result.evidence.after !== undefined && <EvidenceBlock title="Después" value={result.evidence.after} />}
      </div>
      {!!result.evidence.screenshots?.length && (
        <div className="evidence-shots">
          {result.evidence.screenshots.map((screenshot, index) => (
            <a href={screenshot} target="_blank" rel="noreferrer" key={screenshot}>
              <img src={screenshot} alt={"Captura " + (index + 1) + " de la ejecución"} loading="lazy" />
              <span>{index === 0 ? "Antes" : "Después"}</span>
            </a>
          ))}
        </div>
      )}
    </section>
  );
}

function EvidenceBlock({ title, value }: { title: string; value: unknown }) {
  return (
    <details className="evidence-block">
      <summary>{title}</summary>
      <pre>{typeof value === "string" ? value : JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}
