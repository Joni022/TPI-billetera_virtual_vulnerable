import { useCallback, useEffect, useRef, useState } from "react";
import {
  getLabRun,
  getLabRuns,
  getLabStatus,
  HttpError,
  labPost,
} from "../shared/api";
import type { LabResult, LabRun, LabStatus, Variant } from "../shared/types";

import { EXERCISES, MANUAL_SUMMARIES } from "./manualCases";
import type { CaseId, Exercise } from "./manualCases";

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
              <div className="manual-guide">
                <section className="manual-brief" aria-label="Resumen de la prueba manual">
                  <h4>Prueba manual</h4>
                  <p>Restablecé ambas versiones, recargá las billeteras y usá localhost. La contraseña demo es <strong>Demo1234!</strong>. No restablezcas entre variantes.</p>
                  <p><strong>Cómo ejecutarla:</strong> {MANUAL_SUMMARIES[currentExercise.id].execute}</p>
                  <p><strong>Qué se envía:</strong> {MANUAL_SUMMARIES[currentExercise.id].sends}</p>
                  <div className="manual-outcomes">
                    <p><strong>Vulnerable:</strong> {MANUAL_SUMMARIES[currentExercise.id].vulnerable}</p>
                    <p><strong>Corregida:</strong> {MANUAL_SUMMARIES[currentExercise.id].secure}</p>
                  </div>
                  <div className="manual-request">
                    <strong>Petición a observar · HTTP ilustrativo</strong>
                    <p>Esquema para Network/Red, no es código para pegar en Console. Los valores entre ángulos son marcadores.</p>
                    <pre>{currentExercise.request}</pre>
                  </div>
                  {(() => {
                    const snippet = MANUAL_SUMMARIES[currentExercise.id].snippet ?? currentExercise.blocks.find((block) => block.snippet)?.snippet;
                    return snippet && <div className="manual-payload">
                      <div className="manual-request-heading"><strong>{snippet.label}</strong><button className="text-button" type="button" aria-label={"Copiar " + snippet.label} onClick={() => void copyText(snippet.value)}>Copiar</button></div>
                      <pre>{snippet.value}</pre>
                    </div>;
                  })()}
                  {currentExercise.id === "csrf" && <p><a href="http://localhost:5003/" target="_blank" rel="noreferrer">Abrir página atacante de demostración (:5003) ↗</a></p>}
                </section>
                <details className="manual-details" key={currentExercise.id}>
                  <summary>Ver paso a paso</summary>
                <section className="manual-preparation" aria-labelledby="manual-preparation-title">
                  <h4 id="manual-preparation-title">Antes de cada caso</h4>
                  <p>Usá siempre localhost: vulnerable en <a href="http://localhost:5000/" target="_blank" rel="noreferrer">:5000</a>, corregida en <a href="http://localhost:5001/" target="_blank" rel="noreferrer">:5001</a> y esta guía en :5002. Antes de comenzar cada caso, pulsá «Restablecer ambas versiones» arriba y confirmá con «Restablecer ambas». Esperá el mensaje de éxito para ambas: se borran los datos ficticios y se invalidan sesiones y tokens. Recargá las pestañas de las billeteras e ingresá de nuevo. No restablezcas entre las dos variantes de un mismo caso.</p>
                  <p>En el formulario de acceso completá Usuario y Contraseña y pulsá Entrar. La clave demo de ana, bruno y admin es <strong>Demo1234!</strong>. Las pestañas de una misma variante y perfil comparten sesión. Si usás F12, abrilo en la pestaña indicada: Console ejecuta JavaScript; Network/Red permite observar solicitudes y respuestas.</p>
                </section>
                <h4>Paso a paso</h4>
                {currentExercise.id === "csrf" && <p><a href="http://localhost:5003/" target="_blank" rel="noreferrer">Abrir página atacante de demostración (:5003) ↗</a> · El envío ocurre sólo al elegir una variante en esa página.</p>}
                {currentExercise.blocks.map((block) => (
                  <section className="manual-step" key={block.title}>
                    <h5>{block.title}</h5>
                    <ol>{block.steps.map((step) => <li key={step}>{step}</li>)}</ol>
                    {block.snippet && (
                      <div className="manual-payload">
                        <div className="manual-request-heading"><strong>{block.snippet.label}</strong><button className="text-button" type="button" aria-label={"Copiar " + block.snippet.label} onClick={() => void copyText(block.snippet!.value)}>Copiar</button></div>
                        <pre>{block.snippet.value}</pre>
                      </div>
                    )}

                  </section>
                ))}
                <section className="manual-takeaway">
                  <h5>Qué significa</h5><p>{currentExercise.conclusion}</p>
                  <h5>Cómo se corrigió</h5><p>{currentExercise.fix}</p>
                  <h5>Dónde mirar el código</h5><p>{currentExercise.code}</p>
                  <h5>Si el resultado no coincide</h5><p>{currentExercise.recovery}</p>
                </section>
                </details>
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
  const hasCaptures = !!result.evidence.captures?.length;
  const captures = hasCaptures ? result.evidence.captures! : (result.evidence.screenshots ?? []).map((url, index) => {
    const filename = url.split("?")[0].split("/").pop() ?? "";
    const label = /(?:^|[-_.])before(?:[-_.]|$)/i.test(filename) ? "Antes" : /(?:^|[-_.])after(?:[-_.]|$)/i.test(filename) ? "Después" : `Captura ${index + 1}`;
    return { url, label, description: "" };
  });
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
      {!!captures.length && (
        <>
        {!hasCaptures && <p>Capturas de una ejecución anterior, sin la validación visual actual. Reejecutá el caso para generar nuevas evidencias.</p>}
        <div className="evidence-shots">
          {captures.map((capture, index) => (
            <a href={capture.url} target="_blank" rel="noreferrer" key={capture.url + index}>
              <img src={capture.url} alt={capture.description || capture.label + " de la ejecución"} loading="lazy" />
              <span><strong>{capture.label}</strong>{capture.description && <> · {capture.description}</>}</span>
            </a>
          ))}
        </div>
        </>
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
