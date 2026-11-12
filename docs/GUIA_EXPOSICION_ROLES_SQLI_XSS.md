# Guía de exposición de Umbral sobre autorización SQLi y XSS

**Fecha de revisión:** 12 de noviembre de 2026.

Este documento desarrolla tres vulnerabilidades del laboratorio propio: falta de autorización administrativa, inyección SQL en la búsqueda y XSS persistente en el concepto de transferencia. El recorrido de cada tema va desde su significado hasta una demostración local, la petición HTTP, el código que causa la falla, la corrección y la evidencia que permite justificarla. No hace falta conocer previamente Flask o React: los fragmentos se explican por su función.

Las demostraciones se refieren exclusivamente a Umbral con cuentas y dinero ficticios. Las orientaciones para reconocer indicios en una aplicación sirven para estudiar o revisar sistemas propios o autorizados. Un indicio no confirma una vulnerabilidad y la ausencia de un efecto en una prueba no demuestra seguridad completa.

## Cómo usar esta guía para preparar la exposición

1. Leé primero las bases comunes y prepará las pestañas.
2. En cada vulnerabilidad, entendé cuál es la regla que debería cumplirse.
3. Reproducí una operación legítima y después el caso que viola esa regla en la vulnerable.
4. Seguí la entrada desde la pantalla hasta el código. Mostrá la corrección y repetí exactamente el caso en la corregida.
5. Compará datos y efectos, además del código HTTP. Cerrá explicando qué se verificó y qué queda fuera del alcance.

Podés usar los apartados como material de estudio y los guiones breves como apoyo oral. Los ejemplos HTTP son ilustrativos, con cookies y tokens reemplazados por marcadores. Sólo los bloques identificados como ejecutables se pegan en F12; los valores de prueba se pegan en los campos indicados.

## Índice

- [Bases comunes y preparación](#bases-comunes-y-preparación).
- [Cómo reconocer una falla sin sacar conclusiones apresuradas](#cómo-reconocer-una-falla-sin-sacar-conclusiones-apresuradas).
- [Autorización administrativa y control por rol](#1-autorización-por-rol-de-administrador).
- [Inyección SQL en búsqueda de movimientos](#2-inyección-sql-en-la-búsqueda-de-movimientos).
- [XSS persistente en concepto de transferencia](#3-xss-persistente-en-el-concepto-de-transferencia).
- [Ruta de archivos y líneas para la presentación](#ruta-de-archivos-y-líneas-para-la-presentación).
- [Resultados conservados y límites de lo comprobado](#resultados-conservados-y-límites-de-lo-comprobado).

## Bases comunes y preparación

### Qué aplicaciones existen

| Aplicación | Dirección | Función en estos tres ejercicios |
| --- | --- | --- |
| Billetera vulnerable | http://localhost:5000 | Contiene las fallas didácticas. |
| Billetera corregida | http://localhost:5001 | Mismas funciones y controles incorporados. |
| Laboratorio y guía | http://localhost:5002 | Restablece datos, ofrece entradas copiables y conserva evidencia. |

La página del puerto 5003 corresponde a CSRF; **no interviene** en las tres demostraciones de este documento. Roles y SQLi se realizan desde la sesión de Ana. Para XSS, Ana introduce el contenido y Bruno lo visualiza. No hace falta construir una página atacante auxiliar para estos casos.

El frontend es React con TypeScript y el backend es Flask con Python y SQLite. Ambos modos comparten el código y el diseño. La configuración de arranque fija el modo; no se habilita cambiando un campo de una petición. Las bases y las sesiones de cada versión son independientes. Las referencias al código que aparecen abajo corresponden al estado revisado en la fecha indicada.

### Cuentas e importes

| Cuenta | Contraseña ficticia | Rol | Saldo tras restablecer |
| --- | --- | --- | --- |
| ana | Demo1234! | user | 100000 centavos equivalentes a $1.000 |
| bruno | Demo1234! | user | 100000 centavos equivalentes a $1.000 |
| admin | Demo1234! | admin | 100000 centavos equivalentes a $1.000 |

Escribí los nombres en minúsculas. En la pantalla se ingresan pesos y el frontend los convierte a centavos. En la API, amount_cents y delta_cents ya están expresados en centavos: 100 es $1, 2500 es $25 y 5000 es $50.

### Preparación antes de cada vulnerabilidad

1. Si los servicios no están iniciados, ejecutá docker compose up --build desde tpi-billetera con Docker disponible. Si ya están en marcha, no hace falta reiniciarlos para cada ejercicio.
2. Desde el laboratorio, restablecé **ambas versiones** y verificá que ambas terminaron correctamente.
3. Recargá la billetera si conservaba una pantalla anterior e iniciá sesión otra vez. El reset invalida las sesiones; una pantalla abierta no prueba que la sesión siga vigente.
4. Usá localhost en todas las direcciones. No mezcles localhost con 127.0.0.1: las cookies se asocian a hosts diferentes y la pasarela trabaja con localhost.
5. Prepará los datos particulares del caso y no restablezcas a mitad de esa preparación.
6. Ejecutá un caso por vez. No combines el lote automático con operaciones manuales durante la demostración, porque comparten las bases y pueden alterar los resultados.

Cada pestaña de una misma billetera en el mismo perfil comparte la sesión: iniciar sesión como Bruno en una pestaña no mantiene a Ana independiente en otra. Para estos pasos podés cerrar sesión y entrar secuencialmente. Para ver dos cuentas a la vez, necesitás perfiles separados.

### Qué significan sesión token y rol

La cookie permite al servidor recuperar la sesión. current_user consulta la cuenta y su rol en SQLite. El token CSRF se obtiene con GET /api/csrf-token y acompaña las mutaciones normales. El rol determina si esa cuenta puede usar una función administrativa. Obtener un token válido **no concede** el rol admin.

En roles incluimos un token válido para que la corregida llegue a evaluar permisos. En SQLi la prueba es un GET. En XSS enviamos una transferencia legítima con token: su presencia no vuelve seguro interpretar el concepto como HTML. Cada control protege un aspecto diferente.

### Cómo trabajar con F12

Abrí F12 en la pestaña de la billetera que vas a probar, no en la del laboratorio. Las rutas que empiezan con /api apuntan al origen de la pestaña actual. En Network o Red, activá Preserve log y filtrá la ruta relevante. Inspeccioná método, URL, Payload y Response. El saldo y los movimientos se consultan periódicamente cada dos segundos mientras la pantalla está visible, así que puede haber solicitudes adicionales normales.

GET /api/me permite verificar la cuenta real antes de la prueba. Podés abrir http://localhost:5000/api/me en otra pestaña del mismo perfil o consultar esa ruta desde la consola de la billetera. La corregida usa el puerto 5001.

No se necesita Postman. Si lo usaras, tendría su propia sesión y tendrías que preparar sus cookies y tokens; no hereda automáticamente la sesión del navegador. Para esta exposición, la consola y los formularios permiten observar el mismo flujo visible.

## Cómo reconocer una falla sin sacar conclusiones apresuradas

La comprobación parte de una regla explícita y una comparación controlada, no sólo de probar un texto llamativo.

| Caso | Regla esperada | Indicio que orienta la revisión | Evidencia de este laboratorio que confirma el caso |
| --- | --- | --- | --- |
| Roles | Un usuario común no ajusta saldos administrativos. | La API parece accesible aunque el menú esté oculto. | Ana con role user modifica realmente su saldo mediante la ruta administrativa. |
| SQLi | El término filtra datos propios y no modifica la lógica SQL. | La búsqueda produce errores o resultados anómalos ante caracteres especiales. | La respuesta de la API contiene una transferencia entre Admin y Bruno ajena a Ana. |
| XSS | El concepto se representa como contenido, sin ejecutar instrucciones. | Un texto ingresado se transforma en elementos HTML. | Al visualizarlo como Bruno, el navegador ejecuta el marcador que modifica el documento. |

Un menú administrativo oculto puede acompañar una API bien protegida. Un error de búsqueda puede deberse a otra validación. Poder aplicar negrita o ver HTML no acredita por sí solo ejecución de JavaScript. Por eso cada sección enseña a comprobar el efecto concreto, revisar el código y repetir el mismo caso en la corregida.

La automatización de estos casos ya cuenta con una corrida conservada del 8 de noviembre de 2026. Esta guía explica esa evidencia y pasos manuales contrastados con el código; su creación no constituye una nueva ejecución de los ataques ni una auditoría de toda la aplicación.

---

## 1. Autorización por rol de administrador

### Definición y relevancia

La autenticación responde quién inició sesión; la autorización determina qué puede hacer. En Umbral, `admin` puede administrar saldos y una cuenta de rol `user` puede realizar operaciones ordinarias. Existe una falla cuando el servidor verifica que hay una sesión pero no verifica el rol antes de ejecutar una función reservada.

En la versión vulnerable una usuaria autenticada sin privilegios puede alcanzar `POST /api/admin/adjustments` y ajustar su propio saldo. La versión corregida comprueba el rol en el servidor. El caso es **ausencia de autorización por función**: en la demostración Ana modifica su propia cuenta. No es necesario describirlo como IDOR ni afirmar que el ejercicio demostró una modificación de cuenta ajena. Corresponde a [OWASP A01:2025 — Broken Access Control](https://top10.owasp.org/2025/A01_2025-Broken_Access_Control/).

La interfaz sólo incluye Administración en la navegación para `admin` ([WalletApp.tsx, líneas 352 y 447](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/frontend/src/wallet/WalletApp.tsx:352>)). Ocultar el panel orienta al usuario, pero no es una barrera de autorización: una solicitud puede llegar directamente a la API. El servidor debe verificar cada operación sensible.

### Indicios razonables y requisitos

En una revisión autorizada, una señal es que un usuario ordinario alcance una operación reservada y obtenga una respuesta de éxito. La confirmación requiere comprobar el **efecto real** sobre el dato y contrastar con un administrador legítimo. Un botón oculto, una ruta con `admin` en el nombre o un HTTP 200 aislado no prueban por sí solos un problema.

Para este ejercicio: datos restablecidos, Ana autenticada en la variante que se prueba, saldo inicial conocido y cuerpo correcto. En la variante corregida, enviar token CSRF válido permite que la solicitud alcance la comprobación de rol. El token no concede el rol; evita que otra protección rechace antes la solicitud.

### Cómo identificarla desde la web

**Pregunta inicial:** «Si Ana es usuaria común, ¿puede hacer una operación reservada al administrador?». Empezá en la billetera local, sin leer código ni conocer rutas. Con Ana, anotá el saldo y observá que no aparece **Administración**. En F12 → **Red**, filtrá `me` y abrí la respuesta: `user` informa su `id` y `role: "user"`. Si no aparece, recargá. Esto identifica la sesión; no revela la operación administrativa.

Una persona que sólo ve la interfaz de Ana no tiene por qué conocer esa dirección. Una pista posible está en los archivos que la web entrega al navegador: en F12 → **Fuentes/Sources**, buscá globalmente `/api/admin` con Ctrl+Shift+F. Una coincidencia en JavaScript compartido puede señalar una ruta; ni encontrarla ni la ausencia del menú demuestra que el servidor permita usarla. Es una inspección posterior del código entregado al navegador, no algo visible directamente en pantalla. La navegación normal de Ana no genera la solicitud de ajuste.

Para preparar la demostración **en el laboratorio propio y con autorización explícita**, cerrá sesión, ingresá normalmente como `admin` y abrí **Administración** con Red abierto. Seleccioná Ana en **Cuenta**, ingresá `1` peso y un **Motivo**, y pulsá **Aplicar ajuste ficticio**. En Red, seleccioná la solicitud generada: se ven método, URL y campos. Es como mirar el comprobante de una acción que la web acaba de realizar. Revertí con `-1`, cerrá sesión y volvé a entrar como Ana. Sin acceso autorizado a admin, no se puede suponer esta preparación.

Para comprobar la hipótesis, seguí los pasos manuales de abajo: restablecé ambas versiones para recuperar los saldos y volvé a iniciar sesión como Ana. Usá su propio ID y un token válido de su sesión actual, no los de admin. Compará respuesta y saldo en ambas variantes y comprobá también el funcionamiento legítimo de admin.

| Etapa | Qué se observa y qué permite concluir |
| --- | --- |
| Observación | Ana no ve Administración; admin dispone de un formulario de ajuste. |
| Sospecha | Quizá la operación dependa sólo de ocultar la interfaz. Un menú oculto o una ruta conocida no prueban la falla. |
| Prueba | Con sesión `user` y token válido, el ajuste cambia el saldo de Ana en la vulnerable; en la corregida se espera 403 y saldo intacto. Admin conserva la operación legítima. |
| Descartes | Un 200 aislado no alcanza; un 400 por token o un 401 por sesión tampoco demuestra la defensa de rol. |

**Para contar el recorrido:** «Como Ana vi que no tenía Administración. En una preparación autorizada observé la petición que genera el formulario de admin. Verifiqué mi identidad y repetí la operación con mi propia sesión: comparé saldo y respuesta. Después comprobé que admin seguía pudiendo ajustar y revertir».

### Pasos manuales locales

1. En `localhost:5000`, iniciar sesión como `ana`, anotar su saldo `100000` centavos y observar que el menú no ofrece Administración.
2. Abrir en la guía **Autorización y rol de administrador**. La sección muestra una solicitud de ejemplo y permite copiarla. Volver a la pestaña de la billetera vulnerable: la consola debe estar en el origen y sesión de la billetera, no en la guía.
3. Abrir F12 → **Red** para conservar la solicitud y luego **Consola**. Copiar el ejemplo revisado desde la guía y ejecutarlo una sola vez. El ejemplo obtiene `/api/me`, solicita `/api/csrf-token` y envía el ajuste.
4. En Red, abrir `POST /api/admin/adjustments`: el cuerpo incluye el `user_id` de Ana, `delta_cents: 5000` y un motivo. En la evidencia guardada la respuesta es **200**, `{"ok":true}`, y su saldo pasa de `100000` a `105000` centavos: **$50 ficticios**.
5. En `localhost:5001`, iniciar sesión como `ana`, verificar el saldo inicial y repetir desde F12 en esa pestaña. La evidencia guardada muestra **403**, `{"error":"Acceso denegado"}`, y saldo `100000` sin cambios.
6. Control legítimo: en cada variante, cerrar sesión de Ana, ingresar como `admin`, abrir **Administración**, seleccionar `ana`, aplicar `1` peso con un motivo y después `-1` peso para revertir. En la UI el ajuste se ingresa en pesos; la API recibe `delta_cents` de `100` y `-100`. Un administrador legítimo debe poder operar. La automatización registró **200** para el ajuste positivo.

La solicitud puede representarse en HTTP de forma simplificada así:

```http
POST /api/admin/adjustments HTTP/1.1
Host: localhost:5000
Origin: http://localhost:5000
Cookie: wallet_vulnerable=<cookie-de-sesion>
X-CSRF-Token: <token-de-la-sesion>
Content-Type: application/json

{"user_id": 1, "delta_cents": 5000, "reason": "Demostración control de acceso"}
```

El `user_id` 1 es ilustrativo: el ejemplo ejecutable siguiente consulta `/api/me` para obtener el ID real de la sesión. La cookie y el token son marcadores de posición, no valores para copiar; deben corresponder a la sesión utilizada y no deben compartirse.

Ejemplo equivalente al de la guía; toma el ID y token de la sesión actual y está destinado sólo a este laboratorio:

```js
(async () => {
  const me = await (await fetch('/api/me')).json();
  const token = (await (await fetch('/api/csrf-token')).json()).token;
  const response = await fetch('/api/admin/adjustments', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token },
    body: JSON.stringify({
      user_id: me.user.id,
      delta_cents: 5000,
      reason: 'Demostración control de acceso'
    })
  });
  console.log('Estado:', response.status, 'Respuesta:', await response.json());
})();
```

El saldo se refresca periódicamente. No repetir el POST exitoso: sumaría otros 5000 centavos. El resultado `after` del caso automático se captura antes del control legítimo, que luego aplica `+100` y lo revierte con `-100` centavos ([lab/api_cases.py, access_control, líneas 65–91](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/lab/api_cases.py:65>)).

### Recorrido por el código y HTTP

1. `current_user()` obtiene el ID de la sesión, comprueba la generación y consulta el usuario y rol en SQLite ([backend/app.py, líneas 154–164](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:154>)). El rol no se acepta como dato enviado por el cliente.
2. `require_user(admin=False)` responde **401** si no hay sesión válida. En la variante corregida, si se pide administración y el rol no es `admin`, responde **403**. La variante didáctica omite esa segunda verificación por la condición `not teaching`, pero aún exige sesión ([líneas 166–173](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:166>)).
3. `GET /api/admin/users` y `POST /api/admin/adjustments` invocan `require_user(admin=True)` ([líneas 281–290](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:281>)). Luego se validan importe y motivo y se actualiza el saldo en una transacción ([líneas 291–300](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:291>)). La comprobación de rol ocurre antes del cambio.
4. La versión corregida exige además CSRF para mutaciones. Sin token puede responder **400** antes de comprobar el rol. Un 400 no demuestra por sí solo que se haya alcanzado la autorización; con token válido, el resultado esperado de Ana es **403**.

El siguiente fragmento reproduce la función del backend ([backend/app.py, líneas 166–173](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:166>)):

```python
def require_user(admin=False):
    user = current_user()
    if user is None:
        abort(401)
    # Deliberately missing function-level authorization in the teaching app.
    if admin and not teaching and user['role'] != 'admin':
        abort(403)
    return user
```

La variable `teaching` se calcula al crear la aplicación: vale verdadero cuando la variante fija del proceso es `vulnerable` ([línea 42](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:42>)). Para leer la segunda condición, conviene separar sus tres componentes:

1. `admin` indica que quien invocó la función exige acceso administrativo. En `adjust()`, la primera operación del handler es `require_user(admin=True)` ([líneas 288–290](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:288>)).
2. `not teaching` es verdadero en la versión corregida y falso en la vulnerable. Por eso, en la vulnerable la expresión completa no llega a bloquear por rol.
3. `user['role'] != 'admin'` identifica una cuenta autenticada sin ese rol. En corregida, si las tres condiciones son verdaderas, `abort(403)` interrumpe el flujo antes de que se alcance el `UPDATE` de la línea 297. Si el rol es `admin`, la función retorna el usuario y el handler continúa con las validaciones y la transacción.

Para Ana, la UI no dibuja la opción administrativa; sin embargo, la ruta `POST` sigue existiendo. La prueba manual permite mostrar que el cliente puede alcanzar esa ruta y que únicamente el control de la rama corregida detiene la acción. El control positivo con `admin` comprueba que el permiso no se implementó bloqueando a todo el mundo.

La secuencia del `fetch` manual también tiene una finalidad concreta. **Primero**, `GET /api/me` obtiene el identificador de la sesión actual; no se supone que siempre sea un número fijo. **Segundo**, `GET /api/csrf-token` proporciona el token asociado a la sesión activa. **Tercero**, el `POST` envía el ID, los 5000 centavos y el motivo como JSON, e incluye el token en `X-CSRF-Token`. En la versión corregida, el mecanismo CSRF procesa la mutación antes de que el handler llegue a `require_user`. Si el token falta o es inválido, el resultado puede ser 400 y la demostración quedaría detenida en esa primera barrera. Con el token válido, el 403 y el saldo intacto permiten observar la comprobación de rol. El token sirve para la protección CSRF y no transforma a Ana en administradora.

### Ejecución automática, errores y guion

Tras un reinicio exitoso, en la guía seleccionar el caso y **Ejecutar en ambas**. La ejecución guardada informa `attack_reproduced` para vulnerable y `blocked` para corregida, con solicitud, saldos y capturas. Si la sesión cambió, el saldo inicial es distinto o hay interferencia, restablecer e intentar de nuevo; una caída o tiempo agotado no es evidencia de un control efectivo.

- **401 o falta `me.user`:** iniciar sesión como Ana en la misma variante; el reinicio cierra las sesiones.
- **400 en corregida:** revisar token y cuerpo antes de concluir algo sobre el rol.
- **El menú de Ana no ofrece Administración:** es lo esperado; la prueba verifica la API. Con `admin` debe aparecer.
- **429 al entrar:** hay un límite temporal de intentos; esperar o restablecer según la guía.

> «Ana está autenticada, pero no tiene el rol de administradora. Ocultar el panel no controla la API. En la variante vulnerable el servidor omite el rol y su saldo pasa de 100000 a 105000 centavos. En la corregida la misma solicitud con token válido recibe 403 y el saldo no cambia. Un administrador legítimo sí puede aplicar y revertir un ajuste.»

**Preguntas posibles:** ¿Por qué no basta ocultar un botón? Porque la autorización debe estar donde se ejecuta la operación. ¿Qué diferencia hay entre 401 y 403? Falta de sesión válida frente a sesión sin permiso. ¿Se demostró robo de contraseña? No: se demostró una función privilegiada sin el control de rol. ¿Validar el monto basta? No: una cantidad válida también puede venir de una persona no autorizada.

---

## 2. Inyección SQL en la búsqueda de movimientos

### Definición y alcance

Una inyección SQL ocurre cuando datos controlados por quien consulta se incorporan a la estructura de una sentencia y la base los interpreta como instrucciones. En Umbral, la entrada es el parámetro `q` de `GET /api/movements`. Ana ya inició sesión: el ejercicio no evade login, sino que intenta ampliar el alcance de una consulta posterior.

El historial debe devolver sólo transferencias en las que la cuenta autenticada sea emisora o receptora. En la variante vulnerable, la búsqueda se concatena en la sentencia. En la corregida, la estructura permanece fija y los valores se envían como parámetros. Corresponde a [OWASP A05:2025 — Injection](https://top10.owasp.org/2025/A05_2025-Injection/); [OWASP recomienda consultas parametrizadas](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html).

### Indicios y precondiciones

En un sistema autorizado, resultados incompatibles con el filtro, errores de base de datos o respuestas que cambian ante entradas de prueba pueden ser indicios. Ninguno basta por sí solo: un error podría ser de validación y un resultado adicional podría estar autorizado. Para confirmar este caso hay que conocer qué filas pertenecen a Ana y observar si aparece una transacción que no la involucra.

Se necesitan una sesión de Ana y dos movimientos conocidos en cada variante: Ana → Bruno y Admin → Bruno. Ana debería ver el primero y no el segundo. Son transferencias de **$1 ficticio = 100 centavos**. La búsqueda posterior es `GET`; por sí sola no crea ni modifica movimientos.

### Cómo identificarla desde la web

**Pregunta inicial:** «¿La búsqueda filtra únicamente mis movimientos?». Prepará primero las dos filas conocidas siguiendo los pasos 1 y 2 de abajo y volvé a entrar como Ana. En **Actividad**, mirá el campo **Buscar por usuario o concepto** y el botón **Buscar**. Probá primero una búsqueda normal, como `Compra propia`, y luego dejá el campo vacío y buscá de nuevo. F12 → **Red**, filtro `movements`, permite observar la solicitud que genera la propia pantalla y su respuesta; al buscar, `q` transporta el texto. La dirección se descubre mirando esa interacción, sin conocer antes la API. Que aparezca `q` no demuestra cómo se construye la consulta en el servidor.

Para saber si una fila sería ajena no alcanza con mirar un nombre desconocido: prepará y conocé los datos de prueba. En cada variante, Ana envía a Bruno `Compra propia` y admin envía a Bruno `Movimiento reservado`, como se detalla abajo. De vuelta como Ana, confirmá con búsqueda vacía que aparece la primera y no la segunda. Aplicá luego la cadena exacta de la sección siguiente, compará la lista y **Response** con esa base conocida, y repetí en la corregida. Finalmente buscá `Compra propia` para verificar la función legítima. No presupongas que una fila pertenece a otra persona sin ese contexto controlado.

| Etapa | Qué se observa y qué permite concluir |
| --- | --- |
| Observación | La búsqueda envía un término y devuelve movimientos visibles de la cuenta. |
| Sospecha | Un error o cambio inesperado al usar una comilla orienta a investigar; también puede tener otra causa. |
| Prueba | Tras preparar y reconocer ambas filas, aparece para Ana la transferencia admin → Bruno en la vulnerable; en la corregida no aparece y la búsqueda propia funciona. |
| Descartes | Una comilla, un error HTTP, un 200 o una fila cuya pertenencia se desconoce no prueban por sí solos SQLi ni acceso indebido. El código actual devuelve 400 genérico si SQLite rechaza esta búsqueda. |

**Para contar el recorrido:** «Como Ana vi una búsqueda en Actividad. Preparé movimientos con propietarios conocidos y comprobé el resultado normal. Con el término de prueba apareció una fila entre admin y Bruno, que Ana no debería ver; en la corregida no apareció y la búsqueda de Ana siguió funcionando». La revisión posterior de `movements` explica por qué sucedió; la pantalla sola no muestra el SQL interno.

### Preparación y pasos manuales

1. Restablecer ambas versiones. En `localhost:5000`, entrar como `ana`; en **Transferencias**, enviar **$1** a `bruno` con concepto `Compra propia`.
2. Cerrar sesión de Ana. Entrar como `admin`, enviar **$1** a `bruno` con concepto `Movimiento reservado`, cerrar sesión y volver a entrar como `ana` en la misma variante.
3. En **Actividad**, sin búsqueda, comprobar que aparece la operación propia y no la de Admin a Bruno.
4. Copiar de la guía la búsqueda de prueba, pegarla en **Actividad** y presionar **Buscar**:

```text
' OR 1=1 --
```

5. La evidencia guardada de la variante vulnerable muestra **HTTP 200** y dos filas: `Compra propia` y `Movimiento reservado`. La segunda es ajena a Ana. Ese contenido, no sólo el estado HTTP, evidencia la ampliación.
6. Repetir en `localhost:5001`: preparar también allí las dos transferencias y volver a entrar como Ana. Si se restablecen ambas antes de repetir, preparar nuevamente las filas de cada una. La evidencia corregida muestra **HTTP 200** y una lista vacía para la cadena de prueba; no aparece la operación ajena.
7. Control positivo: buscar `Compra propia` como Ana en corregida y comprobar que sí se devuelve su movimiento. Así se verifica que la función de búsqueda legítima continúa operando.

En F12 → **Red**, filtrar `movements`, abrir `GET /api/movements?q=...` y comparar el parámetro, el estado y el arreglo `movements`. El navegador codifica el valor en la URL. **200 en ambas versiones no implica vulnerabilidad en ambas**: hay que revisar qué filas se devolvieron y a quién pertenecen.

Una representación HTTP simplificada de esa búsqueda es:

```http
GET /api/movements?q=%27%20OR%201%3D1%20-- HTTP/1.1
Host: localhost:5000
Cookie: wallet_vulnerable=<cookie-de-sesion>
```

El valor de `q` está codificado para transportarlo en la URL y representa la misma cadena de prueba; la forma exacta de codificación puede variar según el cliente, por ejemplo, algunos pueden dejar la comilla sin codificar. Esta solicitud GET no lleva cuerpo. La cookie es un marcador de posición y debe corresponder a una sesión válida de Ana.

### Consultas expandida y parametrizada

`movements()` exige sesión, obtiene `q` y recorta la búsqueda a 200 caracteres ([backend/app.py, líneas 242–245](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:242>)). Limitar longitud no evita por sí mismo que se altere la sintaxis.

En vulnerable, un `f-string` intercala `q` directamente en el `LIKE` ([líneas 247–254](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:247>)). Si el ID de Ana fuera 1, la parte relevante de la consulta con la cadena de prueba quedaría conceptualmente así:

```python
rows = db.execute(select + f"WHERE (t.sender_id={user['id']} OR t.recipient_id={user['id']}) AND t.concept LIKE '%{q}%' ORDER BY t.id DESC").fetchall()
```

Por comparación, con la búsqueda normal `Compra propia` el fragmento construido sería:

```sql
WHERE (t.sender_id=1 OR t.recipient_id=1)
  AND t.concept LIKE '%Compra propia%' ORDER BY t.id DESC
```

Con la cadena de la demostración, la expansión exacta de ese fragmento es:

```sql
WHERE (t.sender_id=1 OR t.recipient_id=1)
  AND t.concept LIKE '%' OR 1=1 --%' ORDER BY t.id DESC
```

La comilla de entrada cierra el literal, `OR 1=1` agrega una condición verdadera y `--` comenta el resto. La base interpreta esos caracteres como estructura SQL; por eso la condición de propiedad deja de limitar adecuadamente el resultado. La evidencia muestra una fila ficticia ajena; no demuestra modificación, borrado ni extracción de contraseñas.

En corregida, el código mantiene fija la consulta y liga por separado el ID dos veces y el patrón de búsqueda ([líneas 255–257](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:255>)):

```python
rows = db.execute(select + 'WHERE (t.sender_id=? OR t.recipient_id=?) AND t.concept LIKE ? ORDER BY t.id DESC',
    (user['id'], user['id'], '%'+q+'%')).fetchall()
```

```sql
WHERE (t.sender_id=? OR t.recipient_id=?) AND t.concept LIKE ?
```

Los parámetros son, conceptualmente, `(id_ana, id_ana, '%' + q + '%')`. Aunque `q` contenga comillas y palabras SQL, viaja como valor y no cambia la estructura. Los símbolos `%` y `_` conservan su significado de comodines de `LIKE`, pero no modifican la condición que restringe las filas al usuario. Parametrizar no equivale a borrar todos los caracteres especiales.

Cada signo `?` ocupa un lugar de valor: el primero se liga al ID de Ana como remitente, el segundo al mismo ID como destinataria y el tercero al patrón `LIKE` con el contenido de `q` entre `%`. Los `OR`, `AND`, nombres de columnas y paréntesis pertenecen a la sentencia fija; una comilla presente dentro de `q` no se convierte en un delimitador de la consulta.

El recorrido completo ayuda a ubicar la frontera de confianza: el formulario **Actividad** recoge la búsqueda, el navegador la transmite como parámetro `q`, Flask lee ese parámetro y el backend consulta SQLite. La respuesta vuelve como JSON con el arreglo `movements`, y React dibuja las filas. En la vulnerable, el cambio de significado ocurre al formar el SQL en el servidor, no al mostrar el JSON. Codificar el parámetro para que viaje por la URL —por ejemplo, mediante `encodeURIComponent` o `urlencode`— resuelve la representación HTTP; al recibirlo, el servidor recupera el texto. Esa codificación no sustituye los parámetros SQL ni constituye por sí sola una protección frente a la inyección.

### Alternativa automática, errores y guion

Después del reinicio, seleccionar **Inyección SQL en la búsqueda** y **Ejecutar en ambas**. El escenario usa sesiones separadas de Ana y Admin, crea las dos transferencias de 100 centavos, consulta primero el historial normal y después la cadena de prueba ([lab/api_cases.py, sqli, líneas 94–121](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/lab/api_cases.py:94>)). Guarda respuesta y capturas; la ejecución final registró `attack_reproduced` en vulnerable y `blocked` en corregida.

- **No aparece la fila ajena en vulnerable:** verificar que Admin haya transferido a Bruno en esa misma base y volver a entrar como Ana.
- **401:** la sesión venció o fue invalidada por el reinicio; iniciar sesión y preparar de nuevo.
- **Filas de pruebas anteriores:** restablecer y crear sólo las dos filas conocidas; no inferir una fuga a partir de procedencia incierta.
- **400 o error de búsqueda:** es una señal que requiere investigación, no prueba por sí sola de exposición de una fila ajena.
- **200 en corregida:** es compatible con un procesamiento seguro. Verificar que la respuesta no contenga la fila reservada y que una búsqueda legítima sí funcione.
- **Inconcluso o timeout:** revisar servicios y estado; no presentarlo como mitigación verificada.

> «Ana entra normalmente y debería ver sólo transferencias en las que participa. Creamos una propia y otra entre Admin y Bruno. En vulnerable el texto se agrega a la sentencia y altera la condición: aparece también el movimiento reservado. En corregida la estructura es fija, los valores se ligan como parámetros y esa misma búsqueda devuelve cero filas; el historial normal continúa funcionando.»

**Preguntas posibles:** ¿Por qué la corregida responde 200? Porque procesó la búsqueda y el resultado seguro es no devolver datos ajenos. ¿Basta prohibir comillas? No: la defensa mostrada es separar consulta y valores y mantener el filtro de propiedad. ¿Se evade el login? No: Ana ya estaba autenticada. ¿Se borraron datos o se obtuvieron contraseñas? No lo demuestra este caso. ¿Para qué sirve crear una fila propia y otra ajena? La primera controla el funcionamiento normal; la segunda permite comprobar si el alcance se amplió indebidamente.


---

## 3. XSS persistente en el concepto de transferencia

### Propósito y límites de la demostración

Este ejercicio muestra un flujo completo de dato almacenado y renderizado: Ana envía una transferencia ficticia a Bruno y el servidor guarda el concepto. Cuando la interfaz actualiza la Actividad reciente de Ana puede aparecer allí el marcador; luego Bruno vuelve a renderizar el concepto al abrir su Actividad, demostrando el efecto entre usuarios. En la variante vulnerable, el concepto se interpreta como HTML y el navegador crea un marcador visible «XSS ejecutado». En la variante corregida, el mismo dato se conserva y se recibe, pero React lo muestra como texto; no crea el elemento marcador. La comparación aísla la frontera principal del ejercicio: el tratamiento de contenido no confiable al renderizarlo.

El marcador es intencionalmente inocuo. El código de demostración no lee cookies, no extrae datos, no contacta servicios externos y no altera otra cuenta. El objetivo es demostrar que el navegador ejecutó contenido controlado por el usuario, no practicar robo de sesión. Usá sólo las cuentas y las dos instancias locales del laboratorio.

### Concepto en un minuto

Cross-site scripting (XSS) ocurre cuando contenido controlado por alguien termina interpretado como código activo en el navegador de otra persona. El navegador no puede distinguir por sí solo si un fragmento HTML provino de una plantilla confiable o de un campo editable: esa decisión depende de cómo la aplicación lo representa y de las políticas del documento.

Tres categorías frecuentes ayudan a ubicar el caso:

- **Reflejado:** la entrada llega en una petición y se incorpora enseguida a una respuesta, sin guardarse para otra visita.
- **Persistente o almacenado:** la entrada se conserva, por ejemplo en una base de datos, y se vuelve a mostrar a quien consulta el registro más tarde. Este ejercicio pertenece a esta categoría.
- **Basado en DOM:** describe el punto donde el código del cliente toma una fuente controlable y la coloca en un destino que el navegador interpreta como HTML o código. Puede ocurrir sin que el servidor genere una respuesta HTML peligrosa.

Estas etiquetas no son excluyentes: “reflejado” y “persistente” describen cómo llega o se conserva la entrada; “DOM” señala dónde se convierte en contenido activo. Este ejercicio es persistente y la interpretación ocurre en el DOM de React. Ninguna etiqueta por sí sola demuestra que hubo ejecución. Ver caracteres como `<` y `>`, o ver un texto raro, no demuestra XSS. La evidencia positiva es el marcador DOM visible «XSS ejecutado» después de renderizar el concepto como HTML. Puede aparecerle primero a Ana en **Actividad reciente** tras enviar; la demostración de impacto entre usuarios continúa cuando Bruno abre Actividad. En la variante corregida el concepto guardado sigue visible como texto literal, pero el marcador no se crea. La prueba combina el dato persistido con la observación del DOM.

### Requisitos y datos

El proyecto mantiene la guía/runner en http://localhost:5002 y las billeteras en http://localhost:5000 (vulnerable) y http://localhost:5001 (corregida); las dos billeteras comparten interfaz, pero cada instancia tiene su estado de laboratorio separado (docs/GUIA.md, líneas 1–3). La página de http://localhost:5003 corresponde al ejercicio CSRF. No hace falta abrirla para este XSS.

Usá:

| Cuenta | Clave | Función en esta prueba |
| --- | --- | --- |
| ana | Demo1234! | Envía la transferencia |
| bruno | Demo1234! | Abre Actividad y observa el dato |

Las cuentas comienzan con 100000 centavos, equivalentes a $1.000,00 (docs/GUIA.md, líneas 18–26). El importe de la demostración es $1: Ana debe quedar con 99900 centavos y Bruno con 100100, si se parte del estado limpio y no interviene otra operación. Los conceptos están limitados a 200 caracteres en la ruta de transferencia; el texto de prueba tiene 189 caracteres, por lo que cabe en ese campo (backend/app.py, función transfer, líneas 260–279; frontend/src/guide/manualCases.ts, constante xss, línea 29).

Antes de cada variante, en la guía elegí Restablecer datos de ambas versiones y confirmá. El reinicio repone las semillas e invalida sesiones. Después iniciá sesión normalmente en la versión que vas a probar. No asumas que una sesión permanece abierta tras un reinicio (docs/GUIA.md, líneas 5–16). Para la prueba manual, usá una sola variante de principio a fin: enviá como Ana, cerrá esa sesión e ingresá como Bruno en esa misma billetera. Cambiar de 5000 a 5001 entre el envío y la lectura consultaría otra base de datos, así que el movimiento no aparecería allí.

### Cómo identificarla desde la web

**Pregunta inicial:** «¿Qué pasa con un concepto escrito por Ana cuando Bruno recibe la transferencia?». Sin mirar código, entrá como Ana en **Transferencias** y enviá $1 a Bruno con el texto inocuo `Prueba concepto`. En F12 → **Red**, observá la solicitud que genera **Enviar transferencia** y su respuesta; el envío exitoso indica que se registró la operación. Cerrá sesión, recargá la página e ingresá como Bruno en la misma variante: buscá el texto en **Actividad reciente** o **Actividad**. Encontrarlo muestra que el dato persiste y llega a otra cuenta; no demuestra XSS.

Como segunda observación local, cerrá la sesión de Bruno, ingresá de nuevo como Ana y enviá otro $1 a Bruno con `<strong>Prueba concepto</strong>` en **Concepto**. Cerrá sesión, recargá y volvé a entrar como Bruno para observarlo. Si aparece en negrita sin las etiquetas, es un indicio de que se interpretó HTML; no confirma ejecución de JavaScript. Si se ven las etiquetas literalmente, se está tratando como texto en esa salida, que es el comportamiento esperado para este caso; esa observación no certifica todos los contextos de la aplicación. La respuesta en Red puede mostrar el valor almacenado, pero recibir JSON tampoco demuestra que se haya ejecutado nada.

Para confirmar ejecución en este laboratorio propio y autorizado, restablecé ambas versiones para recuperar saldos y movimientos, y usá el marcador exacto de **Texto exacto de prueba** y el recorrido manual que siguen. Iniciá sesión de nuevo tras el reset. El marcador puede aparecer ya en **Actividad reciente** de Ana. Como la aplicación conserva la página al cambiar de sesión, cerrá sesión y recargá antes de entrar como Bruno, o usá perfiles separados: así un marcador previo de Ana no se confunde con una ejecución al mostrar el movimiento a Bruno. Repetí en la corregida y comprobá también que la transferencia legítima llegó. Después, la revisión de `MovementList` permite explicar la causa.

| Etapa | Qué se observa y qué permite concluir |
| --- | --- |
| Observación | Un concepto de Ana aparece luego en el historial de Bruno. |
| Sospecha | Si el texto con `<strong>` se presenta en negrita, hay interpretación de HTML; todavía no se demostró JavaScript. |
| Prueba | Con el marcador exacto, el nodo «XSS ejecutado» aparece al renderizar el dato en la vulnerable; en la corregida el concepto se ve literal y no aparece el marcador. |
| Descartes | Persistencia, HTML en negrita, un 200 o el dato en JSON no bastan para afirmar ejecución. La ausencia de marcador con envío fallido deja la prueba inconclusa. Ejecutar JavaScript en Consola o editar el DOM en Elements no demuestra XSS: debe ejecutarse al renderizar el concepto guardado, sin pegar código en la sesión de Bruno. |

**Para contar el recorrido:** «Como Ana vi que podía escribir un concepto y verifiqué que Bruno lo recibía. Observé cómo se representaba una etiqueta simple; después usé el marcador de prueba y comprobé su ejecución en una sesión limpia de Bruno. En la corregida el texto se conservó y la transferencia llegó sin crear el marcador».

### Texto exacto de prueba

Copiá este valor desde la tarjeta «Concepto de prueba» en la guía. Tiene 189 caracteres y es exactamente el fixture actual definido por la guía (frontend/src/guide/manualCases.ts, constante xss, línea 29, y docs/GUIA.md, líneas 62–74):

```html
<img src=x onerror="document.body.insertAdjacentHTML('afterbegin','<div data-testid=&quot;xss-marker&quot; style=&quot;color:red;font-weight:bold&quot;>XSS ejecutado</div>');this.remove()">
```

El fragmento se compone de cuatro piezas:

1. **Elemento de imagen:** `<img src=x>` pide cargar una imagen relativa llamada x. El servidor local no entrega datos de imagen válidos para ese recurso, de modo que el navegador informa un error de carga o decodificación.
2. **Manejador de error:** onerror contiene JavaScript que se ejecuta cuando falla la imagen, siempre que el documento permita manejadores inline. El manejador inserta un div al comienzo del body y después elimina la imagen rota.
3. **Entidades `&quot;`:** las comillas de atributos del div interno están escritas como entidades porque el manejador externo ya usa comillas dobles. El analizador HTML decodifica esas entidades al procesar el atributo; el JavaScript recibe comillas normales dentro de su cadena entre comillas simples. insertAdjacentHTML recibe entonces el div como HTML y crea el marcador.
4. **Marcador observable:** el div lleva data-testid="xss-marker" y el texto «XSS ejecutado». Ese atributo permite que la automatización local encuentre el nodo; el estilo rojo y negrita lo hace visible durante la explicación.

El servidor no ejecuta el fragmento ni el JSON lo ejecuta: la transferencia guarda el concepto como dato. La ejecución sucede en el navegador cuando una vista interpreta ese dato como HTML. Después del envío, la aplicación actualiza el resumen y puede mostrar el marcador de inmediato en la vista **Actividad reciente** de Ana, porque también reutiliza `MovementList`. Para demostrar el efecto persistente sobre otro usuario, cerrá la sesión de Ana e ingresá como Bruno en la misma variante; su Actividad vuelve a renderizar el mismo movimiento. El código de `Overview` reutiliza `MovementList` en `WalletApp.tsx`, líneas 487–495 y 524–532; el envío refresca los datos mediante `showSuccess`, líneas 365–368, y la consulta de movimientos se realiza en líneas 310–316.

### Recorrido manual: Ana guarda, Bruno observa

#### Variante vulnerable

1. En la guía, elegí XSS persistente en el concepto. Restablecé ambas versiones y confirmá. Abrí la billetera vulnerable en localhost:5000 e iniciá sesión como ana.
2. Entrá en **Transferencias**. En **Usuario destinatario**, escribí bruno; en **Importe en pesos**, escribí 1; en **Concepto**, pegá el valor exacto anterior. Presioná **Enviar transferencia**.
3. La interfaz convierte pesos a centavos: 1 × 100 produce amount_cents: 100. Envía recipient: "bruno", amount_cents: 100 y la cadena de concepto a POST /api/transfers (WalletApp.tsx, función TransferView.submit, líneas 538–565; los campos visibles están en líneas 581–629).
4. Cerrá la sesión de Ana con el control normal de la aplicación y recargá la página antes de ingresar como Bruno. El marcador se inserta directamente en `document.body`, fuera del árbol React, y puede sobrevivir al cambio de vista de la SPA tras el logout. La recarga limpia cualquier marcador que haya creado Ana; también podés usar un perfil de navegador separado para Bruno.
5. Ingresá como bruno en la misma billetera con la clave demo. El concepto puede ejecutarse al cargar el Resumen, dentro de **Actividad reciente**, antes de abrir **Actividad**. Ambas vistas reutilizan `MovementList` (`WalletApp.tsx`, llamada desde `Overview` en línea 532 y desde `MovementsView` en línea 717). Si Ana había visto un marcador antes, la recarga evita atribuirlo a Bruno: cualquier marcador que aparezca después de este login se produjo al renderizar la cuenta de Bruno. Abrí **Actividad** para inspeccionar también la transferencia entrante.

Si el estado era limpio, la cuenta de Bruno muestra $1,00 más y el historial incluye la transferencia. La fila que ve Bruno es el contexto de ejecución relevante. Que Ana haya enviado el contenido no significa que el efecto sólo la afecte a ella: cualquier usuario que renderice ese registro por la rama vulnerable podría activar el mismo contenido.

#### Variante corregida

1. Volvé a la guía y restablecé ambas variantes. Iniciá sesión como Ana en localhost:5001.
2. Repetí el envío de $1 a Bruno con el mismo concepto exacto.
3. Cerrá sesión de Ana y recargá la página antes de ingresar como Bruno; así ambas variantes siguen el mismo procedimiento y la vista empieza sin nodos añadidos por una sesión anterior. Ingresá como Bruno en la billetera corregida.
4. El concepto debe verse literalmente como texto, incluida la cadena que comienza con `<img`, tanto en el Resumen/Actividad reciente como al abrir **Actividad**. No aparece el marcador «XSS ejecutado». El registro y el saldo sí cambian como en la variante vulnerable.

No esperes que el servidor rechace el concepto en esta demostración. El caso fue diseñado para comparar el renderizado; la transferencia válida y el almacenamiento del concepto se permiten en ambas variantes. Si se hace el mismo envío con sesión válida, destinatario válido y saldo suficiente, POST /api/transfers responde 200 en ambas versiones. GET /api/movements devuelve 200 y el concepto guardado en las dos (backend/app.py, función transfer, líneas 260–279, y función movements, líneas 242–258). Un 200 confirma que la petición se aceptó; no demuestra por sí solo ni ausencia ni presencia de XSS.

### Qué hace vulnerable la vista y qué corrige la otra

La API entrega el concepto como dato en la lista de movimientos. El componente MovementList decide después cómo presentarlo. En la rama vulnerable, el código pasa el contenido directamente a dangerouslySetInnerHTML. Esa propiedad le indica a React que debe interpretar el valor como HTML (frontend/src/wallet/WalletApp.tsx, función MovementList, líneas 722–758; en particular la rama vulnerable y la corrección están en líneas 752–757).

```tsx
{variant === "vulnerable" ? (
  <span dangerouslySetInnerHTML={{ __html: movement.concept || "Sin concepto" }} />
) : (
  movement.concept || "Sin concepto"
)}
```

La rama corregida entrega la cadena como un hijo de texto normal. React la escapa para el contexto de texto: el navegador muestra los caracteres en vez de convertirlos en un elemento img, por lo que no existe el manejador onerror que pudiera dispararse. No se está “limpiando” ni borrando el concepto de la base. La protección está en mantenerlo como dato al renderizarlo. Este patrón concreto es seguro para un nodo de texto; otros contextos, como URL, CSS o atributos, requieren reglas adecuadas a su contexto.

El backend valida tipo, longitud, destinatario, importe y saldo, y guarda concept en la fila de transferencia; no transforma este texto para la vista (backend/app.py, función transfer, líneas 260–279). El endpoint de movimientos lo devuelve en JSON (función movements, líneas 242–258). Por eso la frontera importante queda entre recibir/guardar datos y el sumidero de renderizado del frontend.

La variante corregida agrega Content-Security-Policy: default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self' (backend/app.py, función security_headers, líneas 130–136). La aplicación sólo añade esa cabecera cuando no está en la instancia de enseñanza vulnerable. Al no autorizar scripts inline, esta política es una defensa adicional que debería impedir un manejador inline como onerror si llegara a interpretarse. En este ejemplo, React texto ya evita interpretarlo; CSP suma defensa en profundidad. No es un sustituto de escapar correctamente cada dato ni de eliminar el sink HTML inseguro.

### Qué observar en F12

Abrí DevTools con F12 antes de enviar y seleccioná **Network**. Si necesitás conservar las solicitudes al cerrar sesión e ingresar con Bruno, activá **Preserve log**. No compartas cookies, encabezados de sesión ni tokens anti-CSRF en capturas.

- Al pulsar **Enviar transferencia**, la capa de API obtiene primero un token con GET /api/csrf-token y después hace POST /api/transfers con JSON, cookies incluidas y encabezado X-CSRF-Token (frontend/src/shared/api.ts, funciones walletRequest y walletPost, líneas 43–70). Este detalle es parte del contrato general de mutaciones; para el caso XSS, el cuerpo válido se acepta en ambas variantes.
- En el POST, inspeccioná **Payload**: recipient debe ser bruno, amount_cents debe ser 100 y concept debe ser exactamente el texto pegado. La conversión desde pesos ocurre en TransferView.submit, líneas 545–565.
- El estado esperado del POST es 200. Si es distinto, primero resolvé el fallo de autenticación, saldo, destinatario o estado; todavía no hay una comparación de renderizado válida.
- Después de entrar como Bruno y abrir Actividad, buscá GET /api/movements. La respuesta 200 contiene el concepto almacenado. El endpoint limita q a 200 caracteres y devuelve movimientos; la búsqueda no es necesaria para este ejercicio (backend/app.py, líneas 242–258).
- En **Elements**, la variante vulnerable debe tener un elemento marcado data-testid="xss-marker" con texto «XSS ejecutado». En la corregida inspeccioná la fila: el concepto debe permanecer como texto visible y no debe existir el nodo marcador.
- En **Headers**, compará Content-Security-Policy. La respuesta segura incluye la cabecera; en la variante de enseñanza vulnerable se omite de forma deliberada. Una consola sin error no refuta la prueba: el criterio principal es el DOM observado y el dato devuelto.

No esperes necesariamente un aviso de CSP en la variante corregida. Como esa vista representa el contenido como texto, el navegador no tiene que intentar ejecutar onerror. Si ves la cadena literal en la respuesta JSON y también como texto, pero no hay nodo marcador, ése es el resultado corregido esperado.

#### Secuencia HTTP orientativa

Los siguientes bloques representan lo que se observa en DevTools; los marcadores entre ángulos son placeholders, no valores literales para copiar. El ejemplo usa la billetera vulnerable en localhost:5000. Para la corregida, repetí en localhost:5001 después de reiniciar y obtené el token en esa misma sesión. El navegador administra la cookie; no la publiques ni pegues un token real en capturas.

```http
GET /api/csrf-token HTTP/1.1
Host: localhost:5000
Accept: application/json
Cookie: <cookie-de-sesion-de-Ana>

HTTP/1.1 200 OK
Content-Type: application/json

{"token":"<token-CSRF-de-Ana>"}
```

```http
POST /api/transfers HTTP/1.1
Host: localhost:5000
Accept: application/json
Content-Type: application/json
Cookie: <cookie-de-sesion-de-Ana>
X-CSRF-Token: <token-CSRF-de-Ana>

{"recipient":"bruno","amount_cents":100,"concept":"<img src=x onerror=\"document.body.insertAdjacentHTML('afterbegin','<div data-testid=&quot;xss-marker&quot; style=&quot;color:red;font-weight:bold&quot;>XSS ejecutado</div>');this.remove()\">"}

HTTP/1.1 200 OK
Content-Type: application/json

{"ok":true}
```

Tras cerrar la sesión de Ana e iniciar sesión como Bruno, ésta es la consulta del historial. La respuesta esperada es 200 y contiene el movimiento recibido con el valor completo de concept; el cuerpo es JSON, todavía no es la ejecución del navegador.

```http
GET /api/movements HTTP/1.1
Host: localhost:5000
Accept: application/json
Cookie: <cookie-de-sesion-de-Bruno>

HTTP/1.1 200 OK
Content-Type: application/json

{"movements":[{"sender":"ana","recipient":"bruno","amount_cents":100,"concept":"<valor completo del concepto guardado>"}]}
```

El último cuerpo abrevia el concepto sólo para mantener legible el ejemplo: la respuesta real devuelve la cadena de prueba completa. La misma secuencia de lectura se repite en localhost:5001 para comparar el renderizado corregido.

### Automatización desde la guía

El botón **Ejecutar en ambas** corre el caso seleccionado contra ambas billeteras. El runner usa Playwright con contextos de navegador independientes: inicia sesión como Ana en uno y Bruno en otro, sin leer las cookies de la sesión humana. En el contexto receptor guarda una captura inicial, envía la transferencia desde Ana por la interfaz y vuelve a abrir Actividad como Bruno (tests_browser/scenarios.py, run_browser_case, líneas 283–336). El runner verifica el estado 200, que el saldo de Bruno aumentó en 100 centavos, que hay una transferencia nueva y que el concepto recuperado coincide con el fixture.

Para la variante vulnerable, busca un nodo xss-marker cuyo texto sea «XSS ejecutado» y reporta attack_reproduced. En la corregida, exige que el texto completo del payload aparezca en el historial y que no haya nodo marcador; reporta blocked (tests_browser/scenarios.py, líneas 373–403). Las evidencias incluyen solicitud, código HTTP, saldos/conteo antes y después y capturas. La automatización no comparte el navegador visible, aunque opera sobre las mismas bases de las billeteras; el efecto queda en los datos hasta el siguiente reset (docs/GUIA.md, líneas 9–16, 122–125).

Un timeout, una cancelación, una sesión cerrada, una diferencia de saldo inesperada o actividad concurrente debe leerse como inconcluso o error, nunca como “corregido” o “vulnerable” sin la evidencia indicada. El runner devuelve esos estados sin aprobar por ausencia de marcador solamente y cierra sus contextos al finalizar (tests_browser/scenarios.py, líneas 349–371 y 406–449). Si ejecutás la suite completa, el sistema restablece antes de cada ejercicio y las sesiones humanas pueden quedar cerradas; volvé a iniciar sesión normalmente para seguir mirando la billetera.

La página atacante descrita en lab/main.py es exclusivamente para CSRF: su ruta construye un formulario que manda una transferencia entre orígenes (líneas 42–65). No forma parte del flujo XSS y no se necesita para esta exposición.

### Problemas comunes y lectura correcta

- **No aparece la transferencia para Bruno.** Confirma que Ana y Bruno trabajaron en la misma variante y que el POST terminó con 200. Revisa que el destinatario haya sido bruno y que el reset no haya ocurrido entre ambos pasos.
- **La página vuelve al login al pasar de usuario.** Es normal después de cerrar sesión o restablecer datos. Ingresá de nuevo con la cuenta demo; no intentes reutilizar una sesión caducada.
- **El payload visible literal en la corregida parece alarmante.** La cadena almacenada y la respuesta JSON son esperadas. Lo relevante es que se representa como texto y que no se crea el marcador.
- **El marcador no aparece en la vulnerable.** Confirmá que copiaste los 189 caracteres completos, que Bruno abrió Actividad en la misma variante, y que la solicitud se completó. Un concepto truncado, otro caso en ejecución o un estado reiniciado invalida la comparación.
- **El POST devolvió otro estado que 200.** No concluyas que el sistema bloqueó XSS. La prueba de renderizado no se completó; corrige primero el problema de sesión, saldo, destinatario o infraestructura y repite desde un reset limpio.
- **Una captura solo muestra la respuesta JSON.** Eso documenta persistencia del dato, no ejecución. Completá la observación de la vista y confirma el marcador o su ausencia en el DOM.

No se debe afirmar que cualquier HTML es automáticamente XSS ni que el código prueba robo de sesión. Tampoco debe afirmarse que corregir una única vista protege todas las salidas de una aplicación real; este ejercicio compara dos ramas y una ruta concreta. Una revisión completa buscaría otros puntos donde datos no confiables lleguen a sinks HTML y verificaría las defensas en cada contexto.

### Guion oral sugerido

**1. Presentación (30–45 s).** «Voy a seguir un concepto ficticio desde quien lo guarda hasta quien lo ve. Ana envía un peso a Bruno; el concepto persiste. Voy a comparar dos representaciones del mismo dato».

**2. Preparación (30 s).** Mostrá el reset limpio, iniciá sesión como Ana en la variante vulnerable y señalá que el payload está en la tarjeta de la guía. No leas cada carácter: menciona que el contenido está diseñado para insertar un marcador visual y no envía datos afuera.

**3. Recorrido vulnerable (60–90 s).** Enviá la transferencia, indicá que el servidor confirma el registro con HTTP 200 y observá si el marcador aparece ya en el Resumen de Ana. Cerrá sesión y recargá la página para limpiar el marcador insertado directamente en `document.body`; entrá como Bruno. El concepto puede volver a ejecutarse en su Resumen antes de abrir Actividad, porque ambas vistas usan `MovementList`. Explica que el servidor guarda el dato y la ejecución ocurre cuando el navegador lo renderiza. Si tenés DevTools abierto, muestra el nodo marcador creado en la sesión limpia de Bruno.

**4. Recorrido corregido (60–90 s).** Restablecé ambas billeteras, repetí exactamente el mismo envío en la variante corregida y volvé a entrar como Bruno. Señalá que el registro y el saldo cambiaron, el concepto se ve literal y el marcador no existe. Compara la rama de MovementList: dangerouslySetInnerHTML frente al hijo de texto React.

**5. Evidencia y cierre (45–60 s).** En Network muestra el POST 200 y el GET del historial 200 en ambas. En Elements compara DOM. Cierra con la defensa: renderizar como texto, evitar sinks HTML y usar CSP como capa adicional. El status HTTP no distingue por sí solo la seguridad del renderizado.

La duración es orientativa; se puede acortar mostrando primero el caso vulnerable, luego una captura/evidencia automática de ambos resultados. La guía conserva capturas y el resumen de la ejecución; los efectos en la base permanecen hasta el reinicio.

#### Preguntas para conversación

- **¿Por qué Bruno es el observador?** Porque XSS persistente puede afectar a otra persona que consulta el dato guardado; separar emisor y receptor hace visible ese recorrido.
- **¿Por qué el envío responde 200 también en la versión segura?** Porque el backend permite guardar el concepto de prueba. La corrección demostrada cambia cómo se presenta; no depende de que la API filtre esta cadena.
- **¿Qué prueba que hubo ejecución?** El marcador DOM esperado en el recorrido vulnerable, junto con el mismo contenido confirmado en el registro. El aspecto de una cadena por sí solo no basta.
- **¿React siempre resuelve XSS?** No. En este lugar, el texto JSX representa el valor como texto. Usar dangerouslySetInnerHTML, construir atributos inseguros o colocar datos en otros contextos exige analizar esas rutas por separado.
- **¿CSP reemplaza la corrección?** No. Reduce lo que un documento puede ejecutar, pero el programa debe tratar datos no confiables como datos y evitar interpretarlos como HTML.
- **¿Qué cambiarías en producción?** Eliminar el sink HTML, usar renderizado de texto o sanitización robusta cuando haya un requisito legítimo de HTML enriquecido, revisar todas las salidas y mantener CSP estricta como defensa adicional.

---

## Ruta de archivos y líneas para la presentación

Los enlaces siguientes apuntan a archivos reales de esta copia del proyecto. Cada uno abre la línea de inicio relevante. Las referencias del backend para estos recorridos se contrastaron con el archivo actual el 12 de noviembre de 2026; las demás líneas se verificaron el 11 de noviembre; si el código cambia, buscá también el nombre de función o la cadena indicada. Para abrir una ubicación en VS Code podés usar Ctrl+P, escribir la ruta del archivo y agregar :número.

| Abrir el código | Ubicación para buscar manualmente | Qué mostrar |
| --- | --- | --- |
| [Modo vulnerable o corregido](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:42>) | backend/app.py:42 | create_app y variable teaching |
| [Identidad de sesión](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:154>) | backend/app.py:154 | current_user consulta generación y usuario |
| [Comprobación de rol](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:166>) | backend/app.py:166 | require_user |
| [Condición que cambia el resultado de roles](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:171>) | backend/app.py:171 | admin y not teaching y role distinto de admin |
| [Ajuste administrativo](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:288>) | backend/app.py:288 | adjust exige require_user admin antes del UPDATE |
| [Cambio persistido de saldo](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:297>) | backend/app.py:297 | UPDATE parametrizado y registro de ajuste |
| [Menú de administración](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/frontend/src/wallet/WalletApp.tsx:352>) | frontend/src/wallet/WalletApp.tsx:352 | Navegación según rol |
| [Conversión de ajuste en pesos a centavos](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/frontend/src/wallet/WalletApp.tsx:879>) | frontend/src/wallet/WalletApp.tsx:879 | AdminView submit |
| [Consulta de movimientos](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:243>) | backend/app.py:243 | movements obtiene usuario y q |
| [Consulta vulnerable](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:252>) | backend/app.py:252 | Interpolación de q dentro del SQL |
| [Consulta corregida](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:256>) | backend/app.py:256 | SQL con placeholders y valores separados |
| [Construcción de la URL de búsqueda](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/frontend/src/wallet/WalletApp.tsx:437>) | frontend/src/wallet/WalletApp.tsx:437 | encodeURIComponent al aplicar la búsqueda |
| [Importe y envío de la transferencia](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/frontend/src/wallet/WalletApp.tsx:548>) | frontend/src/wallet/WalletApp.tsx:548 | TransferView convierte pesos y envía JSON |
| [Persistencia del concepto](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:278>) | backend/app.py:278 | INSERT de transferencia parametrizado |
| [Representación de conceptos](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/frontend/src/wallet/WalletApp.tsx:722>) | frontend/src/wallet/WalletApp.tsx:722 | MovementList |
| [Punto de ejecución HTML vulnerable](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/frontend/src/wallet/WalletApp.tsx:754>) | frontend/src/wallet/WalletApp.tsx:754 | dangerouslySetInnerHTML |
| [Salida como texto corregida](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/frontend/src/wallet/WalletApp.tsx:756>) | frontend/src/wallet/WalletApp.tsx:756 | Valor normal de React dentro de JSX |
| [Defensa CSP adicional](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:135>) | backend/app.py:135 | Cabecera Content-Security-Policy |
| [Helper común de los POST](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/frontend/src/shared/api.ts:60>) | frontend/src/shared/api.ts:60 | walletPost consulta token y envía el cuerpo |
| [Prueba automática de roles](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/lab/api_cases.py:65>) | lab/api_cases.py:65 | access_control y administrador legítimo |
| [Prueba automática SQLi](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/lab/api_cases.py:94>) | lab/api_cases.py:94 | Preparación de filas y comprobación de fila ajena |
| [Concepto XSS del escenario automático](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/tests_browser/scenarios.py:19>) | tests_browser/scenarios.py:19 | XSS_CONCEPT |
| [Comprobación del marcador en navegador](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/tests_browser/scenarios.py:375>) | tests_browser/scenarios.py:375 | Presencia del elemento y texto del marcador |

### Orden concreto de ventanas durante cada explicación

**Roles:** mostrás Ana y /api/me; ejecutás el POST; mostrás saldo y respuesta; abrís require_user en app.py, luego la llamada de adjust; repetís en corregida y cerrás con el administrador legítimo. No hace falta recorrer todo el archivo de Flask para explicar el permiso.

**SQLi:** mostrás primero las dos transferencias preparadas y cuál pertenece a Ana; ejecutás la búsqueda; mostrás la fila ajena en Response; abrís movements y comparás la línea 252 con las líneas 256 y 257. El frontend sólo transporta y presenta el valor; el motor SQL interpreta la consulta.

**XSS:** mostrás la transferencia con el concepto, cambiás a Bruno y abrís Actividad; mostrás el marcador y el elemento creado; abrís MovementList y comparás las ramas de las líneas 754 y 756; señalás el INSERT como almacenamiento, y CSP como defensa adicional.

## Resultados conservados y límites de lo comprobado

La corrida existente es 000c0cb404874efcbacac65a876213c1. Está registrada como completed y contiene, para estos tres temas, tres attack_reproduced en vulnerable y tres blocked en secure. El estado de la ejecución no reemplaza las observaciones de cada caso.

| Caso | Vulnerable observada | Corregida observada | Control legítimo que debe seguir funcionando |
| --- | --- | --- | --- |
| Autorización | POST 200 y Ana pasa de 100000 a 105000 centavos. | POST 403 y saldo 100000. | El administrador puede ajustar y revertir. |
| SQLi | GET 200 y aparece Movimiento reservado de Admin a Bruno. | GET 200 y lista vacía para el término de prueba, sin fila ajena. | Buscar Compra o limpiar recupera el movimiento propio. |
| XSS persistente | POST 200, concepto guardado y marcador ejecutado al verlo Bruno. | POST 200, concepto guardado como texto sin marcador. | La transferencia de 100 centavos llega a Bruno en ambas. |

Registro completo: [result.json de la corrida conservada](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/evidencias/ejecucion-final/result.json:1>). Las capturas están en [carpeta de evidencias](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/evidencias/ejecucion-final>), dentro de las subcarpetas access-control-vulnerable, access-control-secure, sqli-vulnerable, sqli-secure, xss-vulnerable y xss-secure. Se puede mostrar una captura después de explicar la petición, pero una captura aislada no documenta todo el razonamiento.

**Qué no estamos afirmando:** no se evadió el login con SQLi; no se cambió el rol de Ana; no se robaron cookies ni contraseñas con XSS; no se bloquearon todas las entradas con caracteres especiales. El código corregido cumple los controles de estos escenarios y conserva el negocio legítimo. La prueba combinada de XSS no aísla por separado la contribución de CSP y la de la salida como texto.

Estos pasos manuales se contrastaron con la implementación y con esa evidencia previa. Para preparar este archivo se revisó código y datos existentes; no se lanzó una nueva corrida. Ensayá la secuencia completa en el equipo que utilizarás, y presentá como inconclusa una demostración si faltan la sesión, los datos de preparación o el servicio.

### Ficha breve para registrar un ensayo propio

| Campo | Qué anotar |
| --- | --- |
| Ejercicio y versión | Roles SQLi o XSS, vulnerable o corregida. |
| Preparación | Reset completo, cuenta efectiva, saldo y datos requeridos. |
| Entrada enviada | Campos o término exactos, sin copiar cookies ni tokens. |
| Solicitud | Método y ruta, cuerpo o parámetros pertinentes. |
| Respuesta | Estado y cuerpo relevantes. |
| Efecto | Saldo, fila expuesta o marcador, según el caso. |
| Control legítimo | Operación normal aceptada y datos correctos. |
| Código mostrado | Función, condición y línea que explican el resultado. |
| Conclusión | Falla reproducida, defensa verificada o resultado inconcluso con motivo. |

## Ideas que conectan los tres temas

- **Autenticación y autorización:** estar identificado no concede permiso administrativo.
- **Datos y código:** en SQLi el texto llega a ser sintaxis SQL; en XSS llega a ser HTML y JavaScript en el navegador. Los destinos y los controles son diferentes.
- **Validaciones complementarias:** un token CSRF no verifica roles, una consulta parametrizada no hace seguro el renderizado HTML y una CSP no reemplaza el manejo seguro de la salida.
- **Servidor y cliente:** la interfaz puede ocultar opciones o validar importes, pero la API debe aplicar sus propias reglas. Los conceptos guardados por nuestro backend siguen siendo entrada de usuario cuando se muestran.
- **Estado HTTP y efecto:** 200 puede indicar una operación legítima completada aun cuando se evitó la parte maliciosa. La evidencia central es el cambio real que se pretende impedir.

## Referencias conceptuales

Las descripciones del comportamiento de Umbral proceden de su código y de su registro local. Para estudiar los principios generales, OWASP recomienda comprobar permisos en cada solicitud, separar los valores de la estructura SQL y usar salidas seguras según el contexto, con CSP como capa adicional. Estas fuentes no certifican el proyecto:

- [OWASP sobre autorización y comprobación de permisos](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html).
- [OWASP sobre prevención de inyección SQL mediante parámetros](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html).
- [OWASP sobre prevención de XSS y manejo de la salida](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html).

Como cierre oral: “En los tres casos identificamos una regla, reproducimos una operación que la viola en la versión vulnerable, mostramos la decisión de código responsable y repetimos el escenario con la corrección. La defensa se justifica con el efecto y con el funcionamiento legítimo, no sólo con un mensaje de error”.
