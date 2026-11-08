import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { FormEvent, ReactNode } from "react";
import { HttpError, walletPost, walletRequest, readWalletMeta } from "../shared/api";
import type { Movement, User, Variant, WalletMeta } from "../shared/types";

type View = "overview" | "transfers" | "movements" | "quotes" | "admin";

const NAVIGATION: Array<{ id: View; label: string }> = [
  { id: "overview", label: "Resumen" },
  { id: "transfers", label: "Transferencias" },
  { id: "movements", label: "Actividad" },
  { id: "quotes", label: "Cotizador" },
];

function formatMoney(cents: number): string {
  return new Intl.NumberFormat("es-AR", {
    style: "currency",
    currency: "ARS",
    minimumFractionDigits: 2,
  }).format(cents / 100);
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("es-AR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return "No se pudo completar la operación. Intentá de nuevo.";
}

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export default function WalletApp() {
  const [meta, setMeta] = useState<WalletMeta | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [booting, setBooting] = useState(true);
  const [notice, setNotice] = useState("");

  const loadSession = useCallback(async () => {
    const result = await walletRequest<{ user: User }>("/api/me");
    setUser(result.data.user);
  }, []);

  useEffect(() => {
    let mounted = true;
    void Promise.all([readWalletMeta(), walletRequest<{ user: User }>("/api/me")])
      .then(([walletMeta, account]) => {
        if (!mounted) return;
        setMeta(walletMeta);
        setUser(account.data.user);
      })
      .catch((error: unknown) => {
        if (!mounted) return;
        if (error instanceof HttpError && error.status === 401) {
          void readWalletMeta()
            .then((walletMeta) => {
              if (mounted) setMeta(walletMeta);
            })
            .catch((metaError: unknown) => {
              if (mounted) setNotice(getErrorMessage(metaError));
            });
        } else {
          setNotice(getErrorMessage(error));
        }
      })
      .finally(() => {
        if (mounted) setBooting(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  const handleAuthenticated = useCallback(async () => {
    await loadSession();
    setNotice("");
  }, [loadSession]);

  const handleSessionExpired = useCallback(() => {
    setUser(null);
    setNotice("La sesión terminó. Ingresá de nuevo para continuar.");
  }, []);

  if (booting) {
    return (
      <main className="boot-screen" aria-busy="true">
        <div className="boot-mark" aria-hidden="true">U</div>
        <p>Preparando Umbral…</p>
      </main>
    );
  }

  if (!meta) {
    return (
      <main className="boot-screen">
        <BrandMark />
        <h1>No se pudo conectar con la billetera</h1>
        <p className="body-muted" role="alert">{notice || "Revisá que la aplicación local esté iniciada."}</p>
        <button className="button button-primary" type="button" onClick={() => window.location.reload()}>
          Reintentar
        </button>
      </main>
    );
  }

  if (!user) {
    return (
      <AuthScreen
        variant={meta.variant}
        notice={notice}
        onAuthenticated={handleAuthenticated}
      />
    );
  }

  return (
    <WalletShell
      initialUser={user}
      variant={meta.variant}
      onSessionExpired={handleSessionExpired}
    />
  );
}

function BrandMark() {
  return (
    <a className="brand-lockup" href="/" aria-label="Umbral, inicio">
      <span className="brand-symbol" aria-hidden="true">U</span>
      <span>
        <strong>umbral</strong>
        <small>Billetera de práctica</small>
      </span>
    </a>
  );
}

function VariantTag({ variant }: { variant: Variant }) {
  const vulnerable = variant === "vulnerable";
  return (
    <span className={"variant-tag " + (vulnerable ? "variant-vulnerable" : "variant-secure")}>
      <span className="variant-dot" aria-hidden="true" />
      {vulnerable ? "Entorno vulnerable" : "Entorno corregido"}
    </span>
  );
}

function OtherVariantLink({ variant }: { variant: Variant }) {
  const other = variant === "vulnerable" ? "secure" : "vulnerable";
  const label = other === "secure" ? "corregida" : "vulnerable";
  const url = other === "secure" ? "http://localhost:5001/" : "http://localhost:5000/";
  return (
    <a className="other-variant-link" href={url} target="_blank" rel="noreferrer" aria-label={"Abrir la variante " + label + " en otra pestaña"}>
      {other === "secure" ? "Corregida" : "Vulnerable"} <span aria-hidden="true">↗</span>
    </a>
  );
}

function AuthScreen({
  variant,
  notice,
  onAuthenticated,
}: {
  variant: Variant;
  notice: string;
  onAuthenticated: () => Promise<void>;
}) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [registrationComplete, setRegistrationComplete] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const path = mode === "login" ? "/api/auth/login" : "/api/auth/register";
      await walletPost(path, { username: username.trim(), password });
      if (mode === "register") {
        setRegistrationComplete(true);
        setMode("login");
        setPassword("");
        return;
      }
      await onAuthenticated();
    } catch (submitError) {
      setError(getErrorMessage(submitError));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-layout">
      <header className="auth-header">
        <BrandMark />
        <div className="auth-header-actions">
          <VariantTag variant={variant} />
          <OtherVariantLink variant={variant} />
        </div>
      </header>
      <main className="auth-main">
        <section className="auth-intro">
          <p className="context-label">Laboratorio local · datos ficticios</p>
          <h1>Una billetera para aprender haciendo.</h1>
          <p>Practicá transferencias y revisá cómo responde una aplicación ante distintos ataques.</p>
        </section>
        <section className="auth-panel" aria-labelledby="auth-title">
          <div className="auth-panel-heading">
            <h2 id="auth-title">{mode === "login" ? "Ingresar" : "Crear una cuenta"}</h2>
            <p>{mode === "login" ? "Usá tu cuenta de práctica." : "La cuenta y el saldo son ficticios."}</p>
          </div>
          {notice && <p className="inline-notice" role="status">{notice}</p>}
          {registrationComplete && (
            <p className="inline-success" role="status">La cuenta se creó. Ya podés continuar.</p>
          )}
          <form className="form-stack" onSubmit={submit}>
            <label className="field">
              <span>Usuario</span>
              <input
                data-testid="username"
                autoComplete="username"
                name="username"
                value={username}
                onChange={(event) => setUsername(event.currentTarget.value)}
                required
                maxLength={48}
              />
            </label>
            <label className="field">
              <span>Contraseña</span>
              <input
                data-testid="password"
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                name="password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.currentTarget.value)}
                required
                maxLength={128}
              />
            </label>
            {error && <p className="form-error" role="alert">{error}</p>}
            <button className="button button-primary button-wide" type="submit" disabled={busy} data-testid="login-submit">
              {busy ? "Un momento…" : mode === "login" ? "Entrar" : "Crear cuenta"}
            </button>
          </form>
          <p className="auth-switch">
            {mode === "login" ? "¿Todavía no tenés usuario?" : "¿Ya tenés usuario?"}{" "}
            <button
              className="text-button"
              type="button"
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                setError("");
                setRegistrationComplete(false);
              }}
            >
              {mode === "login" ? "Registrate" : "Ingresá"}
            </button>
          </p>
          <p className="auth-footnote">No ingreses credenciales reales. Esta billetera funciona sólo con información de prueba.</p>
        </section>
      </main>
      <footer className="auth-footer">
        <span>Umbral · práctica local de seguridad</span>
        <span>Sin dinero real · sin servicios externos</span>
      </footer>
    </div>
  );
}

function WalletShell({
  initialUser,
  variant,
  onSessionExpired,
}: {
  initialUser: User;
  variant: Variant;
  onSessionExpired: () => void;
}) {
  const [user, setUser] = useState(initialUser);
  const [view, setView] = useState<View>("overview");
  const [movements, setMovements] = useState<Movement[]>([]);
  const [movementsError, setMovementsError] = useState("");
  const [refreshError, setRefreshError] = useState("");
  const [appliedQuery, setAppliedQuery] = useState("");
  const [toast, setToast] = useState("");
  const inFlight = useRef(false);

  const refreshAccount = useCallback(async () => {
    if (document.hidden || inFlight.current) return;
    inFlight.current = true;
    try {
      const query = appliedQuery ? "?q=" + encodeURIComponent(appliedQuery) : "";
      const [account, movementResult] = await Promise.all([
        walletRequest<{ user: User }>("/api/me"),
        walletRequest<{ movements: Movement[] }>("/api/movements" + query),
      ]);
      setUser(account.data.user);
      setMovements(movementResult.data.movements);
      setMovementsError("");
      setRefreshError("");
    } catch (error) {
      if (error instanceof HttpError && error.status === 401) {
        onSessionExpired();
        return;
      }
      if (!isAbort(error)) setRefreshError("No se pudo actualizar la actividad. Se reintentará automáticamente.");
    } finally {
      inFlight.current = false;
    }
  }, [appliedQuery, onSessionExpired]);

  useEffect(() => {
    void refreshAccount();
    const interval = window.setInterval(() => void refreshAccount(), 2000);
    const onVisible = () => {
      if (!document.hidden) void refreshAccount();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [refreshAccount]);

  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(""), 4200);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  const visibleNav = useMemo(
    () => (user.role === "admin" ? [...NAVIGATION, { id: "admin" as const, label: "Administración" }] : NAVIGATION),
    [user.role],
  );

  async function logout() {
    try {
      await walletPost<{ ok: true }>("/api/auth/logout", {});
    } catch {
      // The session may already have expired; the local screen still returns to sign-in.
    }
    onSessionExpired();
  }

  async function showSuccess(message: string) {
    setToast(message);
    await refreshAccount();
  }

  return (
    <div className="wallet-shell">
      <header className="wallet-topbar">
        <div className="topbar-inner">
          <BrandMark />
          <div className="topbar-meta">
            <VariantTag variant={variant} />
            <OtherVariantLink variant={variant} />
            <div className="account-menu">
              <span className="account-name">{user.username}</span>
              <span className="role-tag">{user.role === "admin" ? "Administración" : "Cuenta de práctica"}</span>
              <button className="button button-quiet button-logout" type="button" onClick={() => void logout()}>
                Salir
              </button>
            </div>
          </div>
        </div>
      </header>
      <div className="wallet-body">
        <aside className="side-rail" aria-label="Navegación principal">
          <p className="rail-label">Tu cuenta</p>
          <nav className="side-nav">
            {visibleNav.map((item) => (
              <button
                key={item.id}
                type="button"
                className={"nav-link " + (view === item.id ? "nav-link-active" : "")}
                aria-current={view === item.id ? "page" : undefined}
                onClick={() => setView(item.id)}
              >
                {item.label}
              </button>
            ))}
          </nav>
          <div className="rail-note">
            <span className="rail-note-mark" aria-hidden="true">i</span>
            <p>Es un entorno local. No uses dinero ni datos personales reales.</p>
          </div>
        </aside>
        <main className="wallet-main">
          <div className="page-meta">
            <span className="breadcrumb">Umbral <span aria-hidden="true">/</span> {visibleNav.find((item) => item.id === view)?.label ?? "Administración"}</span>
            <span className="sync-status"><span className="sync-dot" aria-hidden="true" /> Actualización cada 2 s</span>
          </div>
          {refreshError && <p className="inline-notice refresh-notice" role="status">{refreshError}</p>}
          {toast && <p className="toast-message" role="status">{toast}</p>}
          {view === "overview" && (
            <Overview
              user={user}
              movements={movements.slice(0, 5)}
              variant={variant}
              onNavigate={setView}
            />
          )}
          {view === "transfers" && (
            <TransferView user={user} onSuccess={showSuccess} />
          )}
          {view === "movements" && (
            <MovementsView
              movements={movements}
              query={appliedQuery}
              error={movementsError}
              variant={variant}
              onSearch={async (query) => {
                setMovementsError("");
                setAppliedQuery(query);
                try {
                  const q = query ? "?q=" + encodeURIComponent(query) : "";
                  const result = await walletRequest<{ movements: Movement[] }>("/api/movements" + q);
                  setMovements(result.data.movements);
                } catch (searchError) {
                  setMovementsError(getErrorMessage(searchError));
                }
              }}
            />
          )}
          {view === "quotes" && <QuotesView onSuccess={showSuccess} />}
          {view === "admin" && (
            <AdminView
              user={user}
              onSessionExpired={onSessionExpired}
              onSuccess={showSuccess}
            />
          )}
        </main>
      </div>
      <nav className="mobile-nav" aria-label="Navegación principal">
        {visibleNav.map((item) => (
          <button
            key={item.id}
            type="button"
            className={"mobile-nav-item " + (view === item.id ? "mobile-nav-active" : "")}
            aria-current={view === item.id ? "page" : undefined}
            aria-label={item.label}
            onClick={() => setView(item.id)}
          >
            {item.id === "transfers" ? "Transferir" : item.id === "admin" ? "Admin" : item.label}
          </button>
        ))}
      </nav>
    </div>
  );
}

function PageHeading({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return (
    <div className="page-heading">
      <div>
        <p className="context-label">Billetera de práctica</p>
        <h1 data-testid="wallet-heading">{title}</h1>
        <p className="page-description">{description}</p>
      </div>
      {action}
    </div>
  );
}

function Overview({
  user,
  movements,
  variant,
  onNavigate,
}: {
  user: User;
  movements: Movement[];
  variant: Variant;
  onNavigate: (view: View) => void;
}) {
  return (
    <section>
      <PageHeading
        title={"Hola, " + user.username}
        description="Este es el estado actual de tu cuenta ficticia."
        action={<button className="button button-primary" type="button" onClick={() => onNavigate("transfers")}>Nueva transferencia</button>}
      />
      <div className="overview-grid">
        <section className="balance-panel" aria-label="Saldo disponible">
          <div className="balance-head">
            <span className="balance-label">Saldo disponible</span>
            <span className="account-currency">ARS</span>
          </div>
          <p className="balance-value" data-testid="balance">{formatMoney(user.balance_cents)}</p>
          <div className="balance-foot">
            <span>Cuenta de práctica</span>
            <span>Sin valor monetario</span>
          </div>
        </section>
        <section className="overview-note">
          <p className="context-label">Entorno de prueba</p>
          <h2>{variant === "vulnerable" ? "Variante vulnerable" : "Variante corregida"}</h2>
          <p>Los datos son ficticios y se pueden restablecer desde la guía de seguridad.</p>
          <a href="http://localhost:5002/" target="_blank" rel="noreferrer">Abrir guía de seguridad <span aria-hidden="true">↗</span></a>
        </section>
      </div>
      <section className="section-block">
        <div className="section-title-row">
          <div>
            <h2>Actividad reciente</h2>
            <p>Últimos movimientos de esta cuenta.</p>
          </div>
          <button className="text-button" type="button" onClick={() => onNavigate("movements")}>Ver actividad</button>
        </div>
        <MovementList movements={movements} variant={variant} compact />
      </section>
    </section>
  );
}

function TransferView({ user, onSuccess }: { user: User; onSuccess: (message: string) => Promise<void> }) {
  const [recipient, setRecipient] = useState("");
  const [amount, setAmount] = useState("");
  const [concept, setConcept] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const amountValue = Number(amount.replace(",", "."));
    const amountCents = Math.round(amountValue * 100);
    if (!Number.isFinite(amountValue) || amountCents <= 0) {
      setError("Ingresá un importe mayor que cero.");
      return;
    }
    if (amountCents > user.balance_cents) {
      setError("El importe supera el saldo disponible.");
      return;
    }

    setBusy(true);
    try {
      await walletPost<{ ok: true }>("/api/transfers", {
        recipient: recipient.trim(),
        amount_cents: amountCents,
        concept,
      });
      setRecipient("");
      setAmount("");
      setConcept("");
      await onSuccess("Transferencia registrada.");
    } catch (submitError) {
      setError(getErrorMessage(submitError));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <PageHeading title="Nueva transferencia" description="Mové saldo ficticio entre cuentas de práctica." />
      <div className="form-layout">
        <form className="form-panel form-stack" onSubmit={(event) => void submit(event)}>
          <label className="field">
            <span>Usuario destinatario</span>
            <input
              data-testid="transfer-recipient"
              value={recipient}
              onChange={(event) => setRecipient(event.currentTarget.value)}
              autoComplete="off"
              required
              maxLength={48}
              placeholder="Por ejemplo, bruno"
            />
            <small>Ingresá el nombre de una cuenta de prueba.</small>
          </label>
          <label className="field">
            <span>Importe en pesos</span>
            <div className="input-prefix">
              <span aria-hidden="true">$</span>
              <input
                data-testid="transfer-amount"
                type="number"
                min="0.01"
                step="0.01"
                inputMode="decimal"
                value={amount}
                onChange={(event) => setAmount(event.currentTarget.value)}
                required
                aria-describedby="transfer-balance-hint"
              />
            </div>
            <small id="transfer-balance-hint">Disponible: {formatMoney(user.balance_cents)}</small>
          </label>
          <label className="field">
            <span>Concepto <span className="field-optional">opcional</span></span>
            <input
              data-testid="transfer-concept"
              value={concept}
              onChange={(event) => setConcept(event.currentTarget.value)}
              maxLength={240}
              autoComplete="off"
              placeholder="Para qué es esta transferencia"
            />
            <small>El concepto aparecerá en la actividad de ambas cuentas.</small>
          </label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="form-actions">
            <button className="button button-primary" data-testid="transfer-submit" type="submit" disabled={busy}>
              {busy ? "Procesando…" : "Enviar transferencia"}
            </button>
            <span className="form-note">Sólo se mueve saldo ficticio.</span>
          </div>
        </form>
        <aside className="side-info">
          <p className="context-label">Antes de enviar</p>
          <h2>Revisá los datos</h2>
          <p>El importe se descuenta de tu cuenta y se acredita al destinatario cuando la operación termina correctamente.</p>
          <p className="side-info-emphasis">La guía de seguridad incluye un ejercicio de concepto de transferencia persistente.</p>
        </aside>
      </div>
    </section>
  );
}

function MovementsView({
  movements,
  query,
  error,
  variant,
  onSearch,
}: {
  movements: Movement[];
  query: string;
  error: string;
  variant: Variant;
  onSearch: (query: string) => Promise<void>;
}) {
  const [draft, setDraft] = useState(query);
  const [busy, setBusy] = useState(false);
  const searchTimer = useRef<number | null>(null);

  useEffect(() => () => {
    if (searchTimer.current !== null) window.clearTimeout(searchTimer.current);
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (searchTimer.current !== null) window.clearTimeout(searchTimer.current);
    setBusy(true);
    try {
      await onSearch(draft.trim());
    } finally {
      setBusy(false);
    }
  }

  function changeDraft(value: string) {
    setDraft(value);
    if (searchTimer.current !== null) window.clearTimeout(searchTimer.current);
    searchTimer.current = window.setTimeout(() => {
      searchTimer.current = null;
      setBusy(true);
      void onSearch(value.trim()).finally(() => setBusy(false));
    }, 350);
  }

  async function clearSearch() {
    if (searchTimer.current !== null) window.clearTimeout(searchTimer.current);
    setDraft("");
    setBusy(true);
    try {
      await onSearch("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <PageHeading title="Actividad" description="Buscá y revisá las transferencias de tu cuenta." />
      <form className="search-row" onSubmit={(event) => void submit(event)}>
        <label className="search-field">
          <span className="sr-only">Buscar en movimientos</span>
          <input
            data-testid="movements-search"
            type="search"
            value={draft}
            onChange={(event) => changeDraft(event.currentTarget.value)}
            placeholder="Buscar por usuario o concepto"
          />
        </label>
        <button className="button button-secondary" type="submit" disabled={busy}>
          {busy ? "Buscando…" : "Buscar"}
        </button>
        {query && <button className="button button-quiet" type="button" onClick={() => void clearSearch()}>Limpiar</button>}
      </form>
      {error && <p className="form-error" role="alert">{error}</p>}
      <MovementList movements={movements} variant={variant} />
    </section>
  );
}

function MovementList({
  movements,
  variant,
  compact = false,
}: {
  movements: Movement[];
  variant: Variant;
  compact?: boolean;
}) {
  if (movements.length === 0) {
    return (
      <div className="empty-state">
        <span className="empty-symbol" aria-hidden="true">—</span>
        <h3>Todavía no hay movimientos</h3>
        <p>Cuando hagas una transferencia, va a aparecer acá.</p>
      </div>
    );
  }

  return (
    <>
      <div className={"movement-list " + (compact ? "movement-list-compact" : "")} data-testid="movements-list">
        {movements.map((movement) => (
          <article className="movement-row" key={movement.id}>
            <span className={"movement-direction " + (movement.sender === movement.recipient ? "movement-neutral" : "")} aria-hidden="true">
              {movement.sender ? (movement.sender === movement.recipient ? "↔" : "↗") : "·"}
            </span>
            <div className="movement-detail">
              <strong>{movement.sender} <span aria-hidden="true">→</span> {movement.recipient}</strong>
              <span className="movement-concept">
                {variant === "vulnerable" ? (
                  // Deliberate stored-XSS sink for the vulnerable lab variant only.
                  <span dangerouslySetInnerHTML={{ __html: movement.concept || "Sin concepto" }} />
                ) : (
                  movement.concept || "Sin concepto"
                )}
              </span>
            </div>
            <time className="movement-date" dateTime={movement.created_at}>{formatDate(movement.created_at)}</time>
            <strong className="movement-amount">{formatMoney(movement.amount_cents)}</strong>
          </article>
        ))}
      </div>
      {compact && <p className="list-footnote">Los datos se actualizan mientras esta página está abierta.</p>}
    </>
  );
}

function QuotesView({ onSuccess }: { onSuccess: (message: string) => Promise<void> }) {
  const [url, setUrl] = useState("http://quote-provider:8080/quote/USD");
  const [result, setResult] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setResult(null);
    setBusy(true);
    try {
      const response = await walletPost<{ result: unknown }>("/api/quotes/import", { url });
      setResult(response.data.result);
      await onSuccess("Respuesta del proveedor recibida.");
    } catch (submitError) {
      setError(getErrorMessage(submitError));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <PageHeading title="Cotizador" description="Consultá un proveedor de cotizaciones simulado." />
      <div className="form-layout">
        <form className="form-panel form-stack" onSubmit={(event) => void submit(event)}>
          <label className="field">
            <span>URL del proveedor</span>
            <input
              type="url"
              value={url}
              onChange={(event) => setUrl(event.currentTarget.value)}
              required
              spellCheck={false}
              autoComplete="url"
              placeholder="http://quote-provider:8080/quote/USD"
            />
            <small>El servidor consulta esta dirección y devuelve el resultado.</small>
          </label>
          <div className="quote-examples">
            <button type="button" className="text-button" onClick={() => setUrl("http://quote-provider:8080/quote/USD")}>
              Proveedor de cotización
            </button>
            <button type="button" className="text-button" onClick={() => setUrl("http://private-ledger:8080/demo")}>
              Servicio interno simulado
            </button>
          </div>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="button button-primary" type="submit" disabled={busy}>
            {busy ? "Consultando…" : "Consultar"}
          </button>
        </form>
        <aside className="side-info">
          <p className="context-label">Sólo laboratorio</p>
          <h2>Datos de prueba</h2>
          <p>La cotización y el servicio interno viven dentro de la red local del laboratorio. No uses direcciones públicas o servicios reales.</p>
        </aside>
      </div>
      {result !== null && (
        <section className="result-block" aria-labelledby="quote-result-heading">
          <h2 id="quote-result-heading">Respuesta recibida</h2>
          <pre>{JSON.stringify(result, null, 2)}</pre>
        </section>
      )}
    </section>
  );
}

type AdminUser = User;

function AdminView({
  user,
  onSessionExpired,
  onSuccess,
}: {
  user: User;
  onSessionExpired: () => void;
  onSuccess: (message: string) => Promise<void>;
}) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [targetUser, setTargetUser] = useState("");
  const [delta, setDelta] = useState("");
  const [reason, setReason] = useState("");
  const [loadError, setLoadError] = useState("");
  const [submitError, setSubmitError] = useState("");
  const [busy, setBusy] = useState(false);

  const loadUsers = useCallback(async () => {
    try {
      const result = await walletRequest<{ users: AdminUser[] }>("/api/admin/users");
      setUsers(result.data.users);
      setLoadError("");
    } catch (error) {
      if (error instanceof HttpError && error.status === 401) {
        onSessionExpired();
        return;
      }
      setLoadError(getErrorMessage(error));
    }
  }, [onSessionExpired]);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError("");
    const deltaCents = Math.round(Number(delta.replace(",", ".")) * 100);
    if (!Number.isSafeInteger(deltaCents) || deltaCents === 0) {
      setSubmitError("Ingresá un ajuste distinto de cero.");
      return;
    }
    setBusy(true);
    try {
      await walletPost<{ ok: true }>("/api/admin/adjustments", {
        user_id: Number(targetUser),
        delta_cents: deltaCents,
        reason,
      });
      setDelta("");
      setReason("");
      await loadUsers();
      await onSuccess("Ajuste de prueba aplicado.");
    } catch (error) {
      setSubmitError(getErrorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <PageHeading title="Administración" description="Ajustes ficticios para las cuentas del laboratorio." />
      {user.role !== "admin" && (
        <p className="inline-notice" role="status">Tu cuenta no tiene acceso de administración. La autorización se valida en el servidor.</p>
      )}
      {loadError && <p className="form-error" role="alert">{loadError}</p>}
      {user.role === "admin" && (
        <>
          <form className="form-panel form-stack admin-form" onSubmit={(event) => void submit(event)}>
            <label className="field">
              <span>Cuenta</span>
              <select value={targetUser} onChange={(event) => setTargetUser(event.currentTarget.value)} required>
                <option value="">Elegí una cuenta</option>
                {users.map((account) => (
                  <option value={String(account.id)} key={account.id}>{account.username} · {formatMoney(account.balance_cents)}</option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Ajuste en pesos</span>
              <input type="number" step="0.01" value={delta} onChange={(event) => setDelta(event.currentTarget.value)} required />
            </label>
            <label className="field">
              <span>Motivo</span>
              <input value={reason} onChange={(event) => setReason(event.currentTarget.value)} required maxLength={160} />
            </label>
            {submitError && <p className="form-error" role="alert">{submitError}</p>}
            <button className="button button-primary" type="submit" disabled={busy}>
              {busy ? "Aplicando…" : "Aplicar ajuste ficticio"}
            </button>
          </form>
          <section className="section-block">
            <div className="section-title-row">
              <div><h2>Cuentas</h2><p>Saldo y rol informados por el servidor.</p></div>
              <button className="button button-quiet" type="button" onClick={() => void loadUsers()}>Actualizar</button>
            </div>
            <div className="user-list">
              {users.map((account) => (
                <div className="user-row" key={account.id}>
                  <strong>{account.username}</strong>
                  <span className="role-tag">{account.role}</span>
                  <span>{formatMoney(account.balance_cents)}</span>
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </section>
  );
}
