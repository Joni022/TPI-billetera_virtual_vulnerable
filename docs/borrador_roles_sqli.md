# Autorización por rol e inyección SQL

Este borrador se limita a dos ejercicios de Umbral. Los pasos usan únicamente las billeteras locales y sus cuentas ficticias. Los resultados observados corresponden a la ejecución `000c0cb404874efcbacac65a876213c1`, conservada en [`evidencias/ejecucion-final/result.json`](../evidencias/ejecucion-final/result.json). Una demostración acotada no garantiza que toda la aplicación esté libre de otras fallas.

## Preparación común

Con Docker Desktop activo y las imágenes ya preparadas, ejecutar desde `tpi-billetera`:

```powershell
docker compose up -d --no-build --pull never --wait
```

Este comando no construye ni descarga imágenes; si faltan, seguir el [README](../README.md). Abrir la [guía](http://localhost:5002), la [billetera vulnerable](http://localhost:5000) y la [corregida](http://localhost:5001). Usar `localhost` de forma consistente. En la guía, seleccionar **Restablecer ambas versiones**, confirmar y esperar que ambas terminen. Si el resultado es parcial, reintentar antes de continuar. El reinicio recupera los datos iniciales e invalida las sesiones, pero conserva las evidencias.

Usuarios: `ana`, `bruno` y `admin`; contraseña ficticia `Demo1234!`. Cada cuenta parte de **100000 centavos = $1.000 ficticios**. Cada versión mantiene su propia base y sesión. En F12 → **Red / Network**, filtrar `Fetch/XHR` y conservar el registro si el navegador lo permite. Se pueden comparar método, ruta, estado y respuesta; no mostrar cookies ni tokens en las capturas.

La guía permite hacer la prueba manual o pulsar **Ejecutar en ambas**. El ejecutor usa sesiones propias, no las cookies del presentador, pero modifica las mismas bases visibles. Un caso individual conserva los cambios hasta que se restablezca; si el resultado es inconcluso o inesperado no debe comunicarse como exitoso.

---

## 1. Autorización por rol de administrador

### Definición y relevancia

La autenticación responde quién inició sesión; la autorización determina qué puede hacer. En Umbral, `admin` puede administrar saldos y una cuenta de rol `user` puede realizar operaciones ordinarias. Existe una falla cuando el servidor verifica que hay una sesión pero no verifica el rol antes de ejecutar una función reservada.

En la versión vulnerable una usuaria autenticada sin privilegios puede alcanzar `POST /api/admin/adjustments` y ajustar su propio saldo. La versión corregida comprueba el rol en el servidor. El caso es **ausencia de autorización por función**: en la demostración Ana modifica su propia cuenta. No es necesario describirlo como IDOR ni afirmar que el ejercicio demostró una modificación de cuenta ajena. Corresponde a [OWASP A01:2025 — Broken Access Control](https://top10.owasp.org/2025/A01_2025-Broken_Access_Control/).

La interfaz sólo incluye Administración en la navegación para `admin` ([`WalletApp.tsx`, líneas 352 y 447](../frontend/src/wallet/WalletApp.tsx)). Ocultar el panel orienta al usuario, pero no es una barrera de autorización: una solicitud puede llegar directamente a la API. El servidor debe verificar cada operación sensible.

### Indicios razonables y requisitos

En una revisión autorizada, una señal es que un usuario ordinario alcance una operación reservada y obtenga una respuesta de éxito. La confirmación requiere comprobar el **efecto real** sobre el dato y contrastar con un administrador legítimo. Un botón oculto, una ruta con `admin` en el nombre o un HTTP 200 aislado no prueban por sí solos un problema.

Para este ejercicio: datos restablecidos, Ana autenticada en la variante que se prueba, saldo inicial conocido y cuerpo correcto. En la variante corregida, enviar token CSRF válido permite que la solicitud alcance la comprobación de rol. El token no concede el rol; evita que otra protección rechace antes la solicitud.

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

El saldo se refresca periódicamente. No repetir el POST exitoso: sumaría otros 5000 centavos. El resultado `after` del caso automático se captura antes del control legítimo, que luego aplica `+100` y lo revierte con `-100` centavos ([`lab/api_cases.py`, `access_control`, líneas 65–91](../lab/api_cases.py)).

### Recorrido por el código y HTTP

1. `current_user()` obtiene el ID de la sesión, comprueba la generación y consulta el usuario y rol en SQLite ([`backend/app.py`, líneas 154–164](../backend/app.py)). El rol no se acepta como dato enviado por el cliente.
2. `require_user(admin=False)` responde **401** si no hay sesión válida. En la variante corregida, si se pide administración y el rol no es `admin`, responde **403**. La variante didáctica omite esa segunda verificación por la condición `not teaching`, pero aún exige sesión ([líneas 166–173](../backend/app.py)).
3. `GET /api/admin/users` y `POST /api/admin/adjustments` invocan `require_user(admin=True)` ([líneas 281–290](../backend/app.py)). Luego se validan importe y motivo y se actualiza el saldo en una transacción ([líneas 291–300](../backend/app.py)). La comprobación de rol ocurre antes del cambio.
4. La versión corregida exige además CSRF para mutaciones. Sin token puede responder **400** antes de comprobar el rol. Un 400 no demuestra por sí solo que se haya alcanzado la autorización; con token válido, el resultado esperado de Ana es **403**.

El siguiente fragmento reproduce la función del backend ([`backend/app.py`, líneas 166–173](../backend/app.py)):

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

La variable `teaching` se calcula al crear la aplicación: vale verdadero cuando la variante fija del proceso es `vulnerable` ([línea 42](../backend/app.py)). Para leer la segunda condición, conviene separar sus tres componentes:

1. `admin` indica que quien invocó la función exige acceso administrativo. En `adjust()`, la primera operación del handler es `require_user(admin=True)` ([líneas 288–290](../backend/app.py)).
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

`movements()` exige sesión, obtiene `q` y recorta la búsqueda a 200 caracteres ([`backend/app.py`, líneas 242–245](../backend/app.py)). Limitar longitud no evita por sí mismo que se altere la sintaxis.

En vulnerable, un `f-string` intercala `q` directamente en el `LIKE` ([líneas 247–254](../backend/app.py)). Si el ID de Ana fuera 1, la parte relevante de la consulta con la cadena de prueba quedaría conceptualmente así:

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

En corregida, el código mantiene fija la consulta y liga por separado el ID dos veces y el patrón de búsqueda ([líneas 255–257](../backend/app.py)):

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

Después del reinicio, seleccionar **Inyección SQL en la búsqueda** y **Ejecutar en ambas**. El escenario usa sesiones separadas de Ana y Admin, crea las dos transferencias de 100 centavos, consulta primero el historial normal y después la cadena de prueba ([`lab/api_cases.py`, `sqli`, líneas 94–121](../lab/api_cases.py)). Guarda respuesta y capturas; la ejecución final registró `attack_reproduced` en vulnerable y `blocked` en corregida.

- **No aparece la fila ajena en vulnerable:** verificar que Admin haya transferido a Bruno en esa misma base y volver a entrar como Ana.
- **401:** la sesión venció o fue invalidada por el reinicio; iniciar sesión y preparar de nuevo.
- **Filas de pruebas anteriores:** restablecer y crear sólo las dos filas conocidas; no inferir una fuga a partir de procedencia incierta.
- **400 o error de búsqueda:** es una señal que requiere investigación, no prueba por sí sola de exposición de una fila ajena.
- **200 en corregida:** es compatible con un procesamiento seguro. Verificar que la respuesta no contenga la fila reservada y que una búsqueda legítima sí funcione.
- **Inconcluso o timeout:** revisar servicios y estado; no presentarlo como mitigación verificada.

> «Ana entra normalmente y debería ver sólo transferencias en las que participa. Creamos una propia y otra entre Admin y Bruno. En vulnerable el texto se agrega a la sentencia y altera la condición: aparece también el movimiento reservado. En corregida la estructura es fija, los valores se ligan como parámetros y esa misma búsqueda devuelve cero filas; el historial normal continúa funcionando.»

**Preguntas posibles:** ¿Por qué la corregida responde 200? Porque procesó la búsqueda y el resultado seguro es no devolver datos ajenos. ¿Basta prohibir comillas? No: la defensa mostrada es separar consulta y valores y mantener el filtro de propiedad. ¿Se evade el login? No: Ana ya estaba autenticada. ¿Se borraron datos o se obtuvieron contraseñas? No lo demuestra este caso. ¿Para qué sirve crear una fila propia y otra ajena? La primera controla el funcionamiento normal; la segunda permite comprobar si el alcance se amplió indebidamente.
