# Contrato de la billetera y el laboratorio

Todas las respuestas son JSON. Los errores tienen `{ "error": "mensaje" }` y código HTTP apropiado. Las dos aplicaciones usan los mismos recursos y datos iniciales independientes. Usuario y contraseña iniciales: `ana`, `bruno`, `admin`, con clave `Demo1234!`; saldo inicial 100000 centavos cada uno. El dinero se expresa como enteros de centavos.

## Billetera (mismo origen de la interfaz)

- `GET /api/meta` → `{ "variant": "vulnerable" | "secure" }`.
- `GET /api/csrf-token` → `{ "token": "..." }`; conservar cookie. La versión segura exige `X-CSRF-Token` en todas las mutaciones; acepta también campo de formulario `csrf_token`.
- `POST /api/auth/register` `{username,password}` → `{user}`; `POST /api/auth/login` igual; `POST /api/auth/logout` → `{ok:true}`.
- `GET /api/me` → `{user:{id,username,role,balance_cents}}`; sin sesión: 401.
- `GET /api/movements?q=texto` → `{movements:[{id, sender, recipient, amount_cents, concept, created_at}]}`.
- `POST /api/transfers` JSON o formulario `{recipient,amount_cents,concept}` → `{ok:true}`.
- `GET /api/admin/users` → `{users:[{id,username,role,balance_cents}]}`; `POST /api/admin/adjustments` `{user_id,delta_cents,reason}` → `{ok:true}`. Sólo admin en segura; usuario autenticado en vulnerable.
- `POST /api/quotes/import` `{url}` → `{result: ...}`. URL proveedor `http://quote-provider:8080/quote/USD`; URL interna de demostración `http://private-ledger:8080/demo`.

## Guía y automatización (localhost:5002)

`GET /lab/api/csrf-token` → `{token}`; `POST` exige `X-CSRF-Token` y Origin de la guía. `GET /lab/api/status` → `{active,needs_reset,variants,credentials}`. `POST /lab/api/reset` `{}` restablece ambas; devuelve `{status,variants}`. Una respuesta `partial` impide ejecutar hasta restablecer ambas.

`POST /lab/api/runs` `{case_id, reset_first}` acepta `access-control`, `csrf`, `xss`, `sqli`, `authentication`, `ssrf`; inicia trabajo → `{id,status}`. `GET /lab/api/runs/{id}` devuelve `{id,case_id,status,results,error}`; cada resultado `{variant,outcome,evidence}` con outcome `attack_reproduced`, `blocked`, `unexpected`, `inconclusive`. `POST /lab/api/runs/{id}/cancel` solicita cancelación. `GET /lab/api/runs` devuelve los últimos diez trabajos. Sólo una ejecución o reset activo; 409 si ocupado.

El canal de control de cada backend escucha el puerto interno 9001, no publicado. `POST /internal/reset` recibe `{operation_id}` con UUID y `Authorization: Bearer <token>`; devuelve `{ok:true,generation,operation_id}`. Repetir el mismo identificador es idempotente. `GET /internal/status` con el mismo token informa `{ok:true,generation,operation_id}` para aclarar una respuesta perdida. La guía guarda resultados por separado: un reinicio completo de una instancia y un fallo en la otra producen estado parcial, no rollback distribuido; se debe reintentar el restablecimiento completo antes de otra prueba. La exclusión con transacciones activas se limita a un proceso por instancia y espera hasta diez segundos.

El origen atacante de demostración está en `http://localhost:5003`. Al restablecer se invalidan las sesiones y los datos previos de ambas billeteras; las evidencias quedan en la guía. Las pruebas automáticas usan las bases visibles.

## Integración de escenarios de navegador

`tests_browser/scenarios.py`: `run_browser_case(case_id, variant, base_url, attacker_url, artifact_dir, cancel_event) -> {outcome,evidence}` para `csrf` y `xss`. Cada llamada debe devolver evidencia serializable JSON y no incluir cookies ni tokens. El runner suministra URL localhost, carpeta de artefactos y evento de cancelación.
