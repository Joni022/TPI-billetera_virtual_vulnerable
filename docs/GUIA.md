# Guía de ejercicios

El laboratorio está pensado para demostraciones locales con las cuentas ficticias. Las dos billeteras usan el mismo diseño y bases separadas: vulnerable en `http://localhost:5000` y corregida en `http://localhost:5001`. La guía y el runner están en `http://localhost:5002`; el sitio atacante local del caso CSRF está en `http://localhost:5003`.

## Preparación y flujo

1. Iniciá el laboratorio con `docker compose up --build` desde la carpeta del proyecto.
2. Abrí la guía y elegí un caso.
3. Antes de un caso individual, elegí **Restablecer datos de ambas versiones** y confirmá. Esto repone los datos semilla e invalida todas las sesiones. La evidencia de corridas anteriores se conserva.
4. Para observar la billetera, ingresá normalmente en cada versión con una cuenta demo. El runner usa su propio navegador y sesión; no lee ni usa tu sesión.
5. Elegí **Ejecutar en ambas variantes**. Se ejecutan los dos navegadores contra las billeteras visibles. Los cambios efectivos permanecen para inspeccionarlos hasta el próximo reinicio.
6. Antes del siguiente ejercicio individual, repetí el reinicio y el ingreso.

Para una demostración sin pausas, **Ejecutar los seis** solicita una confirmación y después restablece las dos variantes antes de cada ejercicio. Ejecuta doce verificaciones en secuencia. Al comenzar otro caso, las billeteras pueden quedar con las sesiones humanas cerradas por el reinicio automático. Las capturas y resúmenes se mantienen aunque se reinicien los datos.

Si el reinicio devuelve estado parcial, no inicies otro caso. Volvé a usar **Restablecer datos de ambas versiones** hasta que aparezca completo. Una ejecución ocupada se informa como tal. Cancelar solicita detener el navegador; ya ocurridos efectos y evidencia parcial permanecen. Timeout, cancelación, error o falta de evidencia se informan como inconclusos, cancelados o error, nunca como aprobación.

## Datos de demostración

| Usuario | Clave | Permiso |
| --- | --- | --- |
| `ana` | `Demo1234!` | Usuario |
| `bruno` | `Demo1234!` | Usuario |
| `admin` | `Demo1234!` | Administrador |

Cada cuenta comienza con 100000 centavos ($1.000,00). Los datos son ficticios. En los pasos manuales, volvés a iniciar sesión en la variante que vas a usar después de cada reset.

## 1. Control de acceso por rol

**Objetivo:** comprobar que las rutas de administración validen el rol en el servidor y no sólo que haya una sesión.

**Manual:** restablecé ambas variantes e ingresá como `ana` en cada una. En las herramientas del navegador consultá `GET /api/me` para obtener el identificador ficticio de tu cuenta. Enviá una solicitud `POST /api/admin/adjustments` para ajustar tu propio saldo en 5000 centavos. En la versión vulnerable, ana pasa de 100000 a 105000 centavos; en la corregida, la solicitud se rechaza y el saldo no cambia. Repetí el control legítimo por separado: ingresá como `admin`, aplicá un ajuste de 100 centavos a ana y revertí esos 100 centavos.

```http
POST /api/admin/adjustments
Content-Type: application/json

{"user_id": <id de ana>, "delta_cents": 5000, "reason": "Demostración control de acceso"}
```

Reemplazá `<id de ana>` por el número devuelto por `GET /api/me`. Para el token exigido por la variante corregida, leé `/api/csrf-token` y enviá su valor en `X-CSRF-Token`. El usuario común no debe poder ajustar su propio saldo en la versión corregida; un administrador sí debe poder hacerlo.

**Corrección:** verificar autenticación y rol de administrador en cada operación del servidor; denegar por defecto y probar también el acceso legítimo del administrador.

## 2. CSRF en transferencia

**Objetivo:** verificar si otro origen puede iniciar una transferencia con una sesión ya abierta.

**Manual:** restablecé ambas variantes e ingresá como `ana` en la billetera vulnerable. Abrí la página atacante local `http://localhost:5003/?variant=vulnerable` en otra pestaña del mismo navegador. El formulario real envía $25 a `bruno` con concepto `Demostración CSRF`. Volvé a la billetera y revisá saldo y Actividad. Repetí después del reset con la billetera corregida y `?variant=secure`.

```http
POST /api/transfers
Content-Type: application/x-www-form-urlencoded

recipient=bruno&amount_cents=2500&concept=Demostración+CSRF
```

La versión vulnerable realiza el movimiento; la corregida rechaza la solicitud entre orígenes y conserva el saldo.

**Corrección:** token anti-CSRF único ligado a la sesión en cada mutación, validación del origen y cookies con política apropiada. CORS no sustituye la defensa CSRF.

## 3. XSS persistente en concepto

**Objetivo:** revisar qué ocurre con HTML almacenado en el concepto de una transferencia ficticia.

**Manual:** restablecé ambas variantes e ingresá como `ana`. En Transferencias, enviá $1 a bruno y pegá este concepto. Cerrá la sesión de ana, ingresá como `bruno` y abrí Actividad para ver el movimiento entrante. En la variante vulnerable aparece el marcador “XSS ejecutado”; en la corregida se muestra el texto sin crear el elemento. Repetí tras el reset.

```html
<img src=x onerror="document.body.insertAdjacentHTML('afterbegin','<div data-testid=&quot;xss-marker&quot; style=&quot;color:red;font-weight:bold&quot;>XSS ejecutado</div>');this.remove()">
```

El efecto es intencionalmente inocuo y queda guardado como movimiento ficticio. No pegues datos reales ni otros payloads.

**Corrección:** representar el concepto como texto y evitar sinks HTML. CSP es una defensa adicional, no reemplaza el escape contextual ni permite confiar en el contenido guardado.

## 4. Inyección SQL en búsqueda de actividad

**Objetivo:** comprobar que el texto de búsqueda no cambie la consulta ni revele movimientos ajenos.

**Preparación manual:** restablecé ambas variantes. En una variante, ingresá como ana y creá una transferencia de prueba de ana a bruno. Cerrá sesión e ingresá como admin; creá otra transferencia de admin a bruno. Cerrá sesión y volvé a ingresar como ana. Repetí esta preparación en la otra variante después de su reset.

**Prueba:** abrí Actividad, pegá el texto en el campo de búsqueda y enviá la consulta.

```text
' OR 1=1 --
```

La versión vulnerable puede incluir el movimiento de admin o mostrar error de SQL. La corregida trata la búsqueda como un valor literal y sólo presenta filas permitidas a ana.

**Corrección:** consultas parametrizadas y filtro de propiedad aplicado en el servidor. No interpolar entrada del usuario en SQL.

## 5. Enumeración de cuentas e intentos de login

**Objetivo:** comparar mensajes para usuarios inexistentes y existentes y observar el límite de intentos.

**Manual:** restablecé ambas variantes. En el formulario de login probá `ana` y luego `noexiste`, usando `Incorrecta123!` para ambos. Compará los mensajes. Repetí hasta seis intentos incorrectos sobre `ana` y observa si el servidor limita la frecuencia. Repetí después del reset en la otra variante. El ejercicio usa nombres ficticios y no intenta adivinar la contraseña real de una persona.

La versión vulnerable puede revelar si una cuenta existe y no aplica un límite efectivo. La corregida devuelve una respuesta genérica y limita intentos reiterados.

**Corrección:** mensajes indistinguibles para usuario desconocido y clave incorrecta; limitación temporal de intentos por cuenta y origen, además de monitoreo seguro.

## 6. SSRF en importación de cotización

**Objetivo:** verificar que el servidor sólo acceda al proveedor permitido.

**Manual:** restablecé ambas variantes, ingresá como ana y abrí Cotizador. Consultá primero el proveedor ficticio permitido:

```text
http://quote-provider:8080/quote/USD
```

Después probá el servicio interno ficticio:

```text
http://private-ledger:8080/demo
```

Esos nombres sólo existen en la red interna aislada de Docker; el navegador no los resuelve y la app no debe hacer peticiones a hosts externos. La vulnerable puede devolver el texto del fixture interno; la corregida rechaza el destino y no lo consulta.

**Corrección:** construir la URL desde la allowlist exacta del proveedor ficticio autorizado, validar ruta y formato, desactivar redirecciones y limitar el tiempo y tamaño de respuesta. La corrección debe rechazar el fixture interno; el permiso de la vulnerable queda confinado a esos dos servicios ficticios en la red Docker aislada, sin acceso externo.

## Ejecución automática y lectura de evidencia

Desde la guía, el botón del caso ejecuta ambas variantes y muestra el caso/variante en curso. El lote ejecuta seis casos por dos variantes, con reset antes de cada uno. El runner usa navegadores propios y las mismas bases visibles, con credenciales ficticias. La automatización real del navegador cubre CSRF y XSS; los demás casos usan las interfaces/API reales del laboratorio.

Los estados por variante son:

- **Exposición reproducida:** se observó la conducta vulnerable esperada.
- **Solicitud bloqueada:** la variante corregida rechazó la acción esperada.
- **Inconcluso:** timeout, cancelación, servicio no disponible o evidencia incompleta.
- **Resultado inesperado:** lo observado no coincide con lo esperado.

Revisá para cada resultado solicitud y estado HTTP, datos antes/después y capturas cuando existan. Un caso sólo representa el contraste esperado cuando hay evidencia completa en las dos variantes. Una prueba no sustituye una revisión del código ni cubre fallas fuera del escenario descrito.
