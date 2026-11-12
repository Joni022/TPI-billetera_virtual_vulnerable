# Material de estudio: roles e inyección SQL

Este material acompaña al [guion oral](GUION_ORAL_ROLES_SQLI.md). Es para estudiar con calma. Las pruebas se limitan a nuestras cuentas ficticias y las instancias locales autorizadas. Describimos resultados esperados con datos preparados; si algo falla o falta, el resultado es inconcluso hasta identificar la causa.

## 1. El mapa antes de empezar

El navegador muestra la interfaz React y envía solicitudes a la API. La API es el programa Flask del servidor: recibe solicitudes, comprueba reglas y consulta o actualiza la base SQLite. Una solicitud es un mensaje de ida; una respuesta vuelve con un estado HTTP y, aquí, datos JSON. JSON representa objetos con nombres y valores, por ejemplo `{"role":"user"}`.

La vulnerable está en `http://localhost:5000` y la corregida en `http://localhost:5001`. Usan el mismo código y frontend, con una variante fijada al arrancar cada servidor; tienen bases y sesiones separadas. Los puertos son orígenes distintos, pero las cookies no se separan por puerto: aquí las instancias usan nombres diferentes, `wallet_vulnerable` y `wallet_secure`, y almacenamiento de sesión independiente. Usamos siempre `localhost`; cambiar a `127.0.0.1` cambia el host y puede afectar cookies y validación de origen.

Los usuarios ficticios son `ana`, `bruno` y `admin`, con contraseña de práctica `Demo1234!`. Ana y Bruno tienen rol `user`; admin tiene rol `admin`. Tras restablecer cada saldo es 100000 centavos, equivalentes a $1000. La interfaz pide pesos; la API usa centavos. El reinicio invalida sesiones: recargamos y volvemos a iniciar sesión.

**Autenticación** responde quién es la persona: iniciamos sesión como Ana. **Autorización** responde qué puede hacer: Ana no debería ajustar saldos. La aplicación conserva la sesión en el servidor. El navegador envía una cookie que permite asociar peticiones con esa sesión; no hace falta conocer ni copiar su valor. HttpOnly impide leerla con JavaScript, pero no impide que el navegador la adjunte automáticamente cuando corresponde.

## 2. Cómo observar el intercambio en F12

Con la billetera abierta, F12 abre las herramientas de desarrollo. En **Network** o **Red** se listan las solicitudes hechas desde la página. Abrimos la pestaña antes de realizar la acción, usamos el filtro por nombre, seleccionamos una solicitud y miramos:

1. **Headers/Encabezados:** método, URL, estado y encabezados. `GET` normalmente pide datos; `POST` envía una operación como un ajuste. La ruta identifica la función, por ejemplo `/api/movements`.
2. **Payload/Carga** o **Request:** datos enviados. En un POST JSON el cuerpo contiene campos; en un GET el término puede aparecer en la URL después de `?`, por ejemplo `?q=Compra%20propia`.
3. **Response/Respuesta:** datos devueltos. Los comparamos con las filas preparadas: el estado por sí solo no dice si corresponden a Ana.

La URL, encabezados y respuesta muestran el intercambio, no la consulta interna SQLite. Para confirmar la causa miramos también el código del servidor. **Console/Consola** ejecuta JavaScript en el contexto de esa página; pegamos únicamente código que entendemos y sólo en nuestro laboratorio. **Sources/Fuentes** permite inspeccionar el JavaScript servido al navegador; puede estar compilado. Buscar globalmente `/api/admin` permite encontrar rutas del frontend compartido. Alternativamente, durante la preparación autorizada ingresamos como admin y observamos en Network la operación real. Así descubrimos la ruta a partir de la aplicación, sin adivinarla.

## 3. Roles: reconocer la regla y el indicio

Como Ana vemos que no aparece Administración. Eso es coherente con su rol, pero no prueba que la API rechace una operación administrativa: un cliente puede construir una solicitud sin usar ese botón. En la preparación entramos como admin, realizamos un ajuste pequeño y lo revertimos desde la interfaz; esto verifica el uso legítimo y permite observar la ruta en Network. Después restablecemos para recuperar los saldos y entramos de nuevo como Ana en ambas variantes.

`GET /api/me` devuelve el usuario asociado a la sesión. En la barra de direcciones de la variante correspondiente, la respuesta tiene esta forma; el ID es ilustrativo y puede cambiar:

```json
{"user":{"id":1,"username":"ana","role":"user","balance_cents":100000}}
```

El indicio es que existe una función para ajustar saldo y que la interfaz de Ana no la ofrece. Para confirmar la falla probamos, dentro del laboratorio, si la API ejecuta esa función con la sesión de Ana y si el saldo cambia. No se cambia su rol, no se supone un ID fijo y no se demuestra robo de credenciales.

## 4. Roles: qué viaja en la petición

Este intercambio es **ilustrativo para lectura**, no se pega en la consola. Los valores entre ángulos son marcadores, no credenciales reales; el ID mostrado es un ejemplo. El navegador agrega la cookie automáticamente.

```http
POST /api/admin/adjustments HTTP/1.1
Host: localhost:5000
Content-Type: application/json
X-CSRF-Token: <token-de-la-sesion-actual>
Cookie: <cookie-de-sesion>

{"user_id":1,"delta_cents":5000,"reason":"Demostración control de acceso"}
```

`POST` expresa la operación y la ruta identifica el ajuste. `Host` indica el destino; `Content-Type` informa que el cuerpo es JSON. `user_id` selecciona la cuenta sobre la que se actúa: el script obtiene el de Ana de `/api/me`. `delta_cents` es el cambio: 5000 centavos son $50. `reason` es el motivo. La cookie vincula la petición con la sesión, no es un rol en sí misma.

`X-CSRF-Token` lleva un token obtenido para la sesión actual. La versión corregida exige esa protección para mutaciones; sin token válido puede responder 400 antes de llegar al control de rol. Lo obtenemos para que la prueba llegue a la regla examinada. No es una contraseña ni un permiso de administrador y no convierte a Ana en admin. El navegador puede leer el token emitido para la página de su propio origen; la cookie HttpOnly sigue sin ser legible por el script.

### Script copiable para la consola de nuestra billetera

Abrimos la pestaña de la variante, iniciamos sesión como Ana, verificamos su saldo inicial y pegamos este bloque completo en F12 → Console. Es el mismo de la guía existente. En vulnerable lo ejecutamos **una vez**: volver a ejecutarlo suma otros $50. Repetimos por separado en la pestaña corregida con su propia sesión.

```js
(async () => {
  const meResponse = await fetch("/api/me");
  const me = await meResponse.json();
  if (!meResponse.ok || me.user?.username !== "ana") { console.log("Ingresá como ana", meResponse.status, me); return; }
  const tokenResponse = await fetch("/api/csrf-token");
  const { token } = await tokenResponse.json();
  if (!tokenResponse.ok || !token) { console.log("No se obtuvo el token", tokenResponse.status); return; }
  console.log("Antes (centavos)", me.user.balance_cents);
  const response = await fetch("/api/admin/adjustments", { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": token }, body: JSON.stringify({ user_id: me.user.id, delta_cents: 5000, reason: "Demostración control de acceso" }) });
  console.log("Ajuste HTTP", response.status, await response.json());
  const afterResponse = await fetch("/api/me");
  console.log("Después HTTP", afterResponse.status, await afterResponse.json());
})();
```

Lectura del código, línea por línea:

- `(async () => { ... })();` define una función anónima asíncrona y la ejecuta inmediatamente. `async` permite usar `await`, que espera el resultado de una operación sin escribir una cadena de callbacks.
- `fetch('/api/me')` hace un GET a la misma instancia. `await` espera la respuesta y `.json()` interpreta su cuerpo. El `if` comprueba `ok` y que el nombre sea Ana; `?.` evita fallar si falta `user`. Si no se cumplen, informa y `return` termina: así no confundimos una operación legítima de admin con la prueba de Ana. `me.user.id` será el ID efectivo, sin fijarlo.
- El siguiente GET consulta `/api/csrf-token`; la desestructuración `{ token }` toma esa propiedad del JSON. El segundo `if` comprueba respuesta y token y termina si faltan. `console.log` muestra el saldo inicial en centavos.
- El siguiente `fetch` usa la ruta de ajuste. `method: 'POST'` elige el método; `headers` declara JSON y envía el token; `body` es el contenido. `JSON.stringify` convierte el objeto JavaScript en texto JSON.
- `user_id` toma el ID consultado, `delta_cents` define el aumento y `reason` proporciona el motivo. El navegador adjunta la cookie aplicable automáticamente; no la incluimos manualmente.
- `response.status` muestra el código HTTP; `await response.json()` lee el cuerpo. Finalmente otro GET de `/api/me` obtiene el estado posterior y la última línea muestra su estado y JSON, incluido `balance_cents`. Si aparece una promesa en consola, esperamos estos mensajes y expandimos el objeto.

En vulnerable esperamos `200` y `{"ok":true}`, con saldo `100000 → 105000`. En corregida, con sesión y token válidos, esperamos `403` y `{"error":"Acceso denegado"}`, con saldo aún `100000`. Si el saldo inicial es distinto, no usar esos números como observados. Si no hay `me.user`, revisar la sesión antes de seguir.

| Estado | Significado en este recorrido | Qué hacer |
| --- | --- | --- |
| 200 | La solicitud se procesó; en el ajuste vulnerable esperamos `ok` y cambio de saldo. | Verificar cuerpo y saldo. |
| 401 | Falta una sesión válida o venció. | Volver a ingresar como Ana en esa variante. |
| 400 | Puede faltar o ser inválido el token CSRF, o haber datos inválidos. | Revisar token y cuerpo; no demuestra que el rol se evaluó. |
| 403 | Acceso denegado; con sesión, token y origen correctos, el caso de Ana corresponde al control de rol. También el control de origen puede devolver 403. | Verificar precondiciones y saldo; usar `localhost`. |
| 429 | Límite temporal de intentos de login en corregida. | Esperar según `Retry-After` o restablecer siguiendo la guía; autenticar otra vez. |

## 5. Roles: dónde falla y dónde se corrige

Ambos servidores ejecutan el mismo [backend/app.py, `create_app`](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:24>). Al arrancar, [línea 43](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:43>) fija `teaching` según la variante: verdadero para vulnerable, falso para corregida. No es un parámetro que Ana activa desde el navegador.

En [`adjust`](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:310>), la primera instrucción del handler es `require_user(admin=True)`. Luego valida el cuerpo y llega al `UPDATE` del saldo. [`current_user`](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:164>) obtiene la identidad desde la sesión, verifica su generación y busca el usuario y su rol en la base; no confía en un rol declarado en el cuerpo del POST.

La decisión central está en [`require_user`](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:176>):

```python
def require_user(admin=False):
    user = current_user()
    if user is None:
        abort(401)
    if teaching:
        # Vulnerable: autentica, pero omite la autorización por rol.
        return user
    else:
        # Corregida: las operaciones administrativas exigen ese rol.
        if admin and user['role'] != 'admin':
            abort(403)
        return user
```

`admin=False` es el valor predeterminado de un **argumento booleano de la función**: indica si el llamador exige acceso administrativo. No es el rol del usuario. En `adjust`, `admin=True` activa ese requisito. `user` es el registro autenticado y `user['role']` es el rol obtenido de la base.

1. `current_user()` recupera la identidad; si no hay usuario válido, `abort(401)` interrumpe el flujo.
2. `if teaching` selecciona la variante vulnerable, que devuelve el usuario sin comprobar el rol, incluso si `admin=True`.
3. En el `else`, correspondiente a la corregida, se comprueba `admin and user['role'] != 'admin'`. Con Ana ambas partes son verdaderas y `abort(403)` detiene la operación antes del `UPDATE`.
4. Si el control no se cumple, se devuelve el usuario. Así, admin continúa hacia las validaciones y la operación legítima. La UI decide qué mostrar; el servidor decide si permite ejecutar la operación. El control positivo de admin ayuda a verificar que no se bloqueó a todos.

## 6. SQL: conceptos para entender la búsqueda

SQLite es el motor de base de datos del laboratorio. Guarda filas en tablas: `users` contiene usuarios y `transfers` transferencias, incluyendo IDs de emisor y receptor, importe y concepto. SQL es el lenguaje con el que el backend pide o modifica datos. Una consulta `SELECT` recupera filas; `WHERE` filtra cuáles; `AND` requiere que se cumplan condiciones y `OR` acepta cualquiera de ellas. Los paréntesis agrupan expresiones.

La regla de negocio es: Ana sólo puede consultar una transferencia si su ID coincide con el del emisor **o** el del receptor. Si además busca por concepto, ambas cosas deben cumplirse: pertenencia **y** coincidencia del concepto. `LIKE` compara texto con un patrón. En `'%Compra propia%'`, las comillas delimitan un texto SQL y `%` significa cualquier secuencia de caracteres: se busca el término dentro del concepto. Un guion bajo `_` también es comodín de un carácter en `LIKE`.

En cada variante, después de restablecer, Ana transfiere $1 a Bruno con concepto `Compra propia`; admin transfiere $1 a Bruno con concepto `Movimiento reservado`. Volvemos a Ana. La primera fila le pertenece por ser emisora; en la segunda intervienen admin y Bruno, por lo que es ajena a Ana. En Actividad comprobamos el historial normal y buscamos `Compra propia`. En F12 → Network, filtro `movements`, observamos que la interfaz envía un GET con `q`: esa es la entrada que investigamos, no una prueba automática de vulnerabilidad.

## 7. SQLi: desde indicio hasta prueba

Un error al ingresar una comilla, un cambio extraño de resultados o una respuesta inesperada pueden orientar la investigación. No prueban por sí solos SQLi: un error puede ser una validación y una fila adicional podría estar autorizada. Aquí controlamos la procedencia de las dos filas y podemos comparar. Una búsqueda normal y el historial vacío de filtro sirven como controles; luego ingresamos exactamente:

```text
' OR 1=1 --
```

La interfaz envía el valor en `q` mediante un GET. Ejemplo ilustrativo de intercambio, no código de consola; `%27` representa la comilla y `%20` un espacio en la URL:

```http
GET /api/movements?q=%27%20OR%201%3D1%20-- HTTP/1.1
Host: localhost:5000
Cookie: <cookie-de-sesion-de-Ana>

HTTP/1.1 200 OK
Content-Type: application/json

{"movements":[{"sender":"admin","recipient":"bruno","concept":"Movimiento reservado","amount_cents":100}]}
```

El cuerpo mostrado es **esquemático**: la respuesta real puede incluir más filas y campos como `id` y `created_at`. La evidencia es que el arreglo incluya la fila conocida admin → Bruno en vulnerable. En corregida esperamos también 200, pero para este término y con los datos preparados, `{"movements":[]}`; lo decisivo es que no aparezca la fila ajena. Después volvemos a buscar `Compra propia` y confirmamos que funciona. Una búsqueda no crea ni modifica transferencias. La demostración no evade el login, no extrae contraseñas ni borra la base.

La codificación de URL permite transportar caracteres en una dirección; el servidor recupera el término. `encodeURIComponent` no es una defensa SQL. El punto relevante está en cómo el backend usa ese valor al hablar con SQLite.

## 8. SQLi: seguir la consulta vulnerable

[`movements`](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:264>) exige usuario y lee `q`, con límite de 200 caracteres. En la rama vulnerable, [línea 273](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:273>), un `f-string` de Python inserta los valores directamente en el texto SQL. Con ID de Ana **hipotético** 1 y búsqueda normal, el fragmento queda así:

```sql
WHERE (t.sender_id=1 OR t.recipient_id=1)
  AND t.concept LIKE '%Compra propia%' ORDER BY t.id DESC
```

`t` es un alias de la tabla de transferencias; `sender_id`, `recipient_id` y `concept` son columnas. `ORDER BY t.id DESC` ordena por ID descendente. Si ponemos la cadena de prueba, el fragmento construido queda exactamente:

```sql
WHERE (t.sender_id=1 OR t.recipient_id=1)
  AND t.concept LIKE '%' OR 1=1 --%' ORDER BY t.id DESC
```

La primera comilla de la entrada cierra el literal que comenzó con `'%`. Entonces `OR 1=1` ya no es texto buscado: SQLite lo interpreta como una condición siempre verdadera. `--` inicia un comentario SQL hasta el final de la línea, por lo que el resto `%' ORDER BY ...` deja de ser ejecutado. `AND` tiene precedencia sobre `OR`: se evalúa conceptualmente `(pertenece_a_Ana AND coincide) OR verdadero`. Aunque la fila no pertenezca a Ana, el lado verdadero hace que satisfaga el filtro. Por eso puede aparecer la fila reservada. No hace falta interpretar cada carácter en la exposición, pero entender esta expansión permite explicarlo.

La rama vulnerable captura errores `sqlite3.Error` de esta búsqueda y devuelve `400` con el prefijo `Error de base de datos:` y el detalle de SQLite. Por ejemplo, una comilla sola en Actividad puede mostrar un error de sintaxis; en la corregida se trata como texto y devuelve una lista vacía si no coincide con ningún concepto. Ese error es un indicio, no demuestra por sí solo acceso indebido. Mostrar detalles internos es intencional para este laboratorio; en una aplicación real se usan mensajes genéricos. Si la prueba exacta no muestra la fila esperada, verificamos datos, sesión y variante; no afirmamos éxito.

Después del 400 pueden permanecer en pantalla las filas de la última respuesta exitosa, no el resultado de la consulta inválida. Contrastamos `Status` y `Response` en Network/Red y limpiamos la búsqueda para recuperar el historial.

## 9. SQLi: la corrección y sus límites

En la [rama corregida](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:277>) la estructura se prepara separada de los valores:

```python
rows = db.execute(select + 'WHERE (t.sender_id=? OR t.recipient_id=?) AND t.concept LIKE ? ORDER BY t.id DESC',
    (user['id'], user['id'], '%'+q+'%')).fetchall()
```

Hay tres marcadores `?`: el primero recibe el ID actual para emisor, el segundo el mismo ID para receptor y el tercero el patrón de búsqueda construido con `%` a ambos lados de `q`. La tupla pasa esos tres valores por separado a SQLite. Las comillas y palabras que escribió Ana permanecen dentro del valor: no pueden cerrar un literal ni incorporar un `OR` a la sintaxis. Los comodines `%` y `_` dentro del valor siguen teniendo su significado de `LIKE`, pero no alteran la estructura ni eliminan la condición de propiedad.

Parametrizar resuelve la mezcla de datos y sintaxis en esta consulta; por sí solo no define qué está autorizado a ver un usuario. Es esencial mantener `(sender_id=? OR recipient_id=?)` y ligar ambos valores a la identidad de la sesión. El resultado correcto se verifica con la fila ajena ausente **y** la búsqueda propia funcionando. Tampoco se prueba seguridad universal de la aplicación: demostramos estas reglas en estos escenarios.

## 10. Preguntas rápidas para ensayar

- **¿Por qué la UI no alcanza?** Porque una solicitud puede enviarse sin usar el botón; el servidor debe comprobar permisos antes de actuar.
- **¿Para qué consultar `/api/me`?** Para verificar identidad y obtener el ID efectivo de Ana; no suponemos que sea 1.
- **¿El token da permiso?** No. Permite satisfacer una protección CSRF; el rol se verifica por separado en el servidor.
- **¿Por qué 200 en SQLi corregida?** La búsqueda fue procesada correctamente. Hay que mirar sus filas, no exigir un error.
- **¿Por qué conocer la fila reservada?** Porque permite demostrar que Ana recibió una transferencia en la que no participa.
- **¿Por qué no alcanza limitar longitud o codificar la URL?** Ninguno separa por sí mismo la estructura SQL de los valores.
- **¿Qué pasa si cae un servicio o la preparación no coincide?** El resultado es inconcluso. Se revisa el estado y se repite la preparación antes de afirmar un resultado.

Referencias de esta copia: [guía detallada de tres temas](GUIA_EXPOSICION_ROLES_SQLI_XSS.md), [código del backend](../backend/app.py) y [contratos de API](API.md). Las observaciones descritas son expectativas basadas en el código y evidencia previa; este documento no representa una nueva ejecución.
