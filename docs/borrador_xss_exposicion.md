# Borrador para exponer: XSS persistente en el concepto de una transferencia

## Propósito y límites de la demostración

Este ejercicio muestra un flujo completo de dato almacenado y renderizado: Ana envía una transferencia ficticia a Bruno y el servidor guarda el concepto. Cuando la interfaz actualiza la Actividad reciente de Ana puede aparecer allí el marcador; luego Bruno vuelve a renderizar el concepto al abrir su Actividad, demostrando el efecto entre usuarios. En la variante vulnerable, el concepto se interpreta como HTML y el navegador crea un marcador visible «XSS ejecutado». En la variante corregida, el mismo dato se conserva y se recibe, pero React lo muestra como texto; no crea el elemento marcador. La comparación aísla la frontera principal del ejercicio: el tratamiento de contenido no confiable al renderizarlo.

El marcador es intencionalmente inocuo. El código de demostración no lee cookies, no extrae datos, no contacta servicios externos y no altera otra cuenta. El objetivo es demostrar que el navegador ejecutó contenido controlado por el usuario, no practicar robo de sesión. Usá sólo las cuentas y las dos instancias locales del laboratorio.

## Concepto en un minuto

Cross-site scripting (XSS) ocurre cuando contenido controlado por alguien termina interpretado como código activo en el navegador de otra persona. El navegador no puede distinguir por sí solo si un fragmento HTML provino de una plantilla confiable o de un campo editable: esa decisión depende de cómo la aplicación lo representa y de las políticas del documento.

Tres categorías frecuentes ayudan a ubicar el caso:

- **Reflejado:** la entrada llega en una petición y se incorpora enseguida a una respuesta, sin guardarse para otra visita.
- **Persistente o almacenado:** la entrada se conserva, por ejemplo en una base de datos, y se vuelve a mostrar a quien consulta el registro más tarde. Este ejercicio pertenece a esta categoría.
- **Basado en DOM:** describe el punto donde el código del cliente toma una fuente controlable y la coloca en un destino que el navegador interpreta como HTML o código. Puede ocurrir sin que el servidor genere una respuesta HTML peligrosa.

Estas etiquetas no son excluyentes: “reflejado” y “persistente” describen cómo llega o se conserva la entrada; “DOM” señala dónde se convierte en contenido activo. Este ejercicio es persistente y la interpretación ocurre en el DOM de React. Ninguna etiqueta por sí sola demuestra que hubo ejecución. Ver caracteres como `<` y `>`, o ver un texto raro, no demuestra XSS. La evidencia positiva es el marcador DOM visible «XSS ejecutado» después de renderizar el concepto como HTML. Puede aparecerle primero a Ana en **Actividad reciente** tras enviar; la demostración de impacto entre usuarios continúa cuando Bruno abre Actividad. En la variante corregida el concepto guardado sigue visible como texto literal, pero el marcador no se crea. La prueba combina el dato persistido con la observación del DOM.

## Requisitos y datos

El proyecto mantiene la guía/runner en http://localhost:5002 y las billeteras en http://localhost:5000 (vulnerable) y http://localhost:5001 (corregida); las dos billeteras comparten interfaz, pero cada instancia tiene su estado de laboratorio separado (docs/GUIA.md, líneas 1–3). La página de http://localhost:5003 corresponde al ejercicio CSRF. No hace falta abrirla para este XSS.

Usá:

| Cuenta | Clave | Función en esta prueba |
| --- | --- | --- |
| ana | Demo1234! | Envía la transferencia |
| bruno | Demo1234! | Abre Actividad y observa el dato |

Las cuentas comienzan con 100000 centavos, equivalentes a $1.000,00 (docs/GUIA.md, líneas 18–26). El importe de la demostración es $1: Ana debe quedar con 99900 centavos y Bruno con 100100, si se parte del estado limpio y no interviene otra operación. Los conceptos están limitados a 200 caracteres en la ruta de transferencia; el texto de prueba tiene 189 caracteres, por lo que cabe en ese campo (backend/app.py, función transfer, líneas 260–279; frontend/src/guide/GuideApp.tsx, XSS_PAYLOAD, líneas 27–30).

Antes de cada variante, en la guía elegí Restablecer datos de ambas versiones y confirmá. El reinicio repone las semillas e invalida sesiones. Después iniciá sesión normalmente en la versión que vas a probar. No asumas que una sesión permanece abierta tras un reinicio (docs/GUIA.md, líneas 5–16). Para la prueba manual, usá una sola variante de principio a fin: enviá como Ana, cerrá esa sesión e ingresá como Bruno en esa misma billetera. Cambiar de 5000 a 5001 entre el envío y la lectura consultaría otra base de datos, así que el movimiento no aparecería allí.

## Texto exacto de prueba

Copiá este valor desde la tarjeta «Concepto de prueba» en la guía. Tiene 189 caracteres y es exactamente el fixture actual definido por la guía (frontend/src/guide/GuideApp.tsx, líneas 27–30, y docs/GUIA.md, líneas 62–74):

```html
<img src=x onerror="document.body.insertAdjacentHTML('afterbegin','<div data-testid=&quot;xss-marker&quot; style=&quot;color:red;font-weight:bold&quot;>XSS ejecutado</div>');this.remove()">
```

El fragmento se compone de cuatro piezas:

1. **Elemento de imagen:** `<img src=x>` pide cargar una imagen relativa llamada x. El servidor local no entrega datos de imagen válidos para ese recurso, de modo que el navegador informa un error de carga o decodificación.
2. **Manejador de error:** onerror contiene JavaScript que se ejecuta cuando falla la imagen, siempre que el documento permita manejadores inline. El manejador inserta un div al comienzo del body y después elimina la imagen rota.
3. **Entidades `&quot;`:** las comillas de atributos del div interno están escritas como entidades porque el manejador externo ya usa comillas dobles. El analizador HTML decodifica esas entidades al procesar el atributo; el JavaScript recibe comillas normales dentro de su cadena entre comillas simples. insertAdjacentHTML recibe entonces el div como HTML y crea el marcador.
4. **Marcador observable:** el div lleva data-testid="xss-marker" y el texto «XSS ejecutado». Ese atributo permite que la automatización local encuentre el nodo; el estilo rojo y negrita lo hace visible durante la explicación.

El servidor no ejecuta el fragmento ni el JSON lo ejecuta: la transferencia guarda el concepto como dato. La ejecución sucede en el navegador cuando una vista interpreta ese dato como HTML. Después del envío, la aplicación actualiza el resumen y puede mostrar el marcador de inmediato en la vista **Actividad reciente** de Ana, porque también reutiliza `MovementList`. Para demostrar el efecto persistente sobre otro usuario, cerrá la sesión de Ana e ingresá como Bruno en la misma variante; su Actividad vuelve a renderizar el mismo movimiento. El código de `Overview` reutiliza `MovementList` en `WalletApp.tsx`, líneas 487–495 y 524–532; el envío refresca los datos mediante `showSuccess`, líneas 365–368, y la consulta de movimientos se realiza en líneas 310–316.

## Recorrido manual: Ana guarda, Bruno observa

### Variante vulnerable

1. En la guía, elegí XSS persistente en el concepto. Restablecé ambas versiones y confirmá. Abrí la billetera vulnerable en localhost:5000 e iniciá sesión como ana.
2. Entrá en **Transferencias**. En **Usuario destinatario**, escribí bruno; en **Importe en pesos**, escribí 1; en **Concepto**, pegá el valor exacto anterior. Presioná **Enviar transferencia**.
3. La interfaz convierte pesos a centavos: 1 × 100 produce amount_cents: 100. Envía recipient: "bruno", amount_cents: 100 y la cadena de concepto a POST /api/transfers (WalletApp.tsx, función TransferView.submit, líneas 538–565; los campos visibles están en líneas 581–629).
4. Cerrá la sesión de Ana con el control normal de la aplicación y recargá la página antes de ingresar como Bruno. El marcador se inserta directamente en `document.body`, fuera del árbol React, y puede sobrevivir al cambio de vista de la SPA tras el logout. La recarga limpia cualquier marcador que haya creado Ana; también podés usar un perfil de navegador separado para Bruno.
5. Ingresá como bruno en la misma billetera con la clave demo. El concepto puede ejecutarse al cargar el Resumen, dentro de **Actividad reciente**, antes de abrir **Actividad**. Ambas vistas reutilizan `MovementList` (`WalletApp.tsx`, llamada desde `Overview` en línea 532 y desde `MovementsView` en línea 717). Si Ana había visto un marcador antes, la recarga evita atribuirlo a Bruno: cualquier marcador que aparezca después de este login se produjo al renderizar la cuenta de Bruno. Abrí **Actividad** para inspeccionar también la transferencia entrante.

Si el estado era limpio, la cuenta de Bruno muestra $1,00 más y el historial incluye la transferencia. La fila que ve Bruno es el contexto de ejecución relevante. Que Ana haya enviado el contenido no significa que el efecto sólo la afecte a ella: cualquier usuario que renderice ese registro por la rama vulnerable podría activar el mismo contenido.

### Variante corregida

1. Volvé a la guía y restablecé ambas variantes. Iniciá sesión como Ana en localhost:5001.
2. Repetí el envío de $1 a Bruno con el mismo concepto exacto.
3. Cerrá sesión de Ana y recargá la página antes de ingresar como Bruno; así ambas variantes siguen el mismo procedimiento y la vista empieza sin nodos añadidos por una sesión anterior. Ingresá como Bruno en la billetera corregida.
4. El concepto debe verse literalmente como texto, incluida la cadena que comienza con `<img`, tanto en el Resumen/Actividad reciente como al abrir **Actividad**. No aparece el marcador «XSS ejecutado». El registro y el saldo sí cambian como en la variante vulnerable.

No esperes que el servidor rechace el concepto en esta demostración. El caso fue diseñado para comparar el renderizado; la transferencia válida y el almacenamiento del concepto se permiten en ambas variantes. Si se hace el mismo envío con sesión válida, destinatario válido y saldo suficiente, POST /api/transfers responde 200 en ambas versiones. GET /api/movements devuelve 200 y el concepto guardado en las dos (backend/app.py, función transfer, líneas 260–279, y función movements, líneas 242–258). Un 200 confirma que la petición se aceptó; no demuestra por sí solo ni ausencia ni presencia de XSS.

## Qué hace vulnerable la vista y qué corrige la otra

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

## Qué observar en F12

Abrí DevTools con F12 antes de enviar y seleccioná **Network**. Si necesitás conservar las solicitudes al cerrar sesión e ingresar con Bruno, activá **Preserve log**. No compartas cookies, encabezados de sesión ni tokens anti-CSRF en capturas.

- Al pulsar **Enviar transferencia**, la capa de API obtiene primero un token con GET /api/csrf-token y después hace POST /api/transfers con JSON, cookies incluidas y encabezado X-CSRF-Token (frontend/src/shared/api.ts, funciones walletRequest y walletPost, líneas 43–70). Este detalle es parte del contrato general de mutaciones; para el caso XSS, el cuerpo válido se acepta en ambas variantes.
- En el POST, inspeccioná **Payload**: recipient debe ser bruno, amount_cents debe ser 100 y concept debe ser exactamente el texto pegado. La conversión desde pesos ocurre en TransferView.submit, líneas 545–565.
- El estado esperado del POST es 200. Si es distinto, primero resolvé el fallo de autenticación, saldo, destinatario o estado; todavía no hay una comparación de renderizado válida.
- Después de entrar como Bruno y abrir Actividad, buscá GET /api/movements. La respuesta 200 contiene el concepto almacenado. El endpoint limita q a 200 caracteres y devuelve movimientos; la búsqueda no es necesaria para este ejercicio (backend/app.py, líneas 242–258).
- En **Elements**, la variante vulnerable debe tener un elemento marcado data-testid="xss-marker" con texto «XSS ejecutado». En la corregida inspeccioná la fila: el concepto debe permanecer como texto visible y no debe existir el nodo marcador.
- En **Headers**, compará Content-Security-Policy. La respuesta segura incluye la cabecera; en la variante de enseñanza vulnerable se omite de forma deliberada. Una consola sin error no refuta la prueba: el criterio principal es el DOM observado y el dato devuelto.

No esperes necesariamente un aviso de CSP en la variante corregida. Como esa vista representa el contenido como texto, el navegador no tiene que intentar ejecutar onerror. Si ves la cadena literal en la respuesta JSON y también como texto, pero no hay nodo marcador, ése es el resultado corregido esperado.

### Secuencia HTTP orientativa

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

## Automatización desde la guía

El botón **Ejecutar en ambas** corre el caso seleccionado contra ambas billeteras. El runner usa Playwright con contextos de navegador independientes: inicia sesión como Ana en uno y Bruno en otro, sin leer las cookies de la sesión humana. En el contexto receptor guarda una captura inicial, envía la transferencia desde Ana por la interfaz y vuelve a abrir Actividad como Bruno (tests_browser/scenarios.py, run_browser_case, líneas 283–336). El runner verifica el estado 200, que el saldo de Bruno aumentó en 100 centavos, que hay una transferencia nueva y que el concepto recuperado coincide con el fixture.

Para la variante vulnerable, busca un nodo xss-marker cuyo texto sea «XSS ejecutado» y reporta attack_reproduced. En la corregida, exige que el texto completo del payload aparezca en el historial y que no haya nodo marcador; reporta blocked (tests_browser/scenarios.py, líneas 373–403). Las evidencias incluyen solicitud, código HTTP, saldos/conteo antes y después y capturas. La automatización no comparte el navegador visible, aunque opera sobre las mismas bases de las billeteras; el efecto queda en los datos hasta el siguiente reset (docs/GUIA.md, líneas 9–16, 122–125).

Un timeout, una cancelación, una sesión cerrada, una diferencia de saldo inesperada o actividad concurrente debe leerse como inconcluso o error, nunca como “corregido” o “vulnerable” sin la evidencia indicada. El runner devuelve esos estados sin aprobar por ausencia de marcador solamente y cierra sus contextos al finalizar (tests_browser/scenarios.py, líneas 349–371 y 406–449). Si ejecutás la suite completa, el sistema restablece antes de cada ejercicio y las sesiones humanas pueden quedar cerradas; volvé a iniciar sesión normalmente para seguir mirando la billetera.

La página atacante descrita en lab/main.py es exclusivamente para CSRF: su ruta construye un formulario que manda una transferencia entre orígenes (líneas 42–65). No forma parte del flujo XSS y no se necesita para esta exposición.

## Problemas comunes y lectura correcta

- **No aparece la transferencia para Bruno.** Confirma que Ana y Bruno trabajaron en la misma variante y que el POST terminó con 200. Revisa que el destinatario haya sido bruno y que el reset no haya ocurrido entre ambos pasos.
- **La página vuelve al login al pasar de usuario.** Es normal después de cerrar sesión o restablecer datos. Ingresá de nuevo con la cuenta demo; no intentes reutilizar una sesión caducada.
- **El payload visible literal en la corregida parece alarmante.** La cadena almacenada y la respuesta JSON son esperadas. Lo relevante es que se representa como texto y que no se crea el marcador.
- **El marcador no aparece en la vulnerable.** Confirmá que copiaste los 189 caracteres completos, que Bruno abrió Actividad en la misma variante, y que la solicitud se completó. Un concepto truncado, otro caso en ejecución o un estado reiniciado invalida la comparación.
- **El POST devolvió otro estado que 200.** No concluyas que el sistema bloqueó XSS. La prueba de renderizado no se completó; corrige primero el problema de sesión, saldo, destinatario o infraestructura y repite desde un reset limpio.
- **Una captura solo muestra la respuesta JSON.** Eso documenta persistencia del dato, no ejecución. Completá la observación de la vista y confirma el marcador o su ausencia en el DOM.

No se debe afirmar que cualquier HTML es automáticamente XSS ni que el código prueba robo de sesión. Tampoco debe afirmarse que corregir una única vista protege todas las salidas de una aplicación real; este ejercicio compara dos ramas y una ruta concreta. Una revisión completa buscaría otros puntos donde datos no confiables lleguen a sinks HTML y verificaría las defensas en cada contexto.

## Guion oral sugerido

**1. Presentación (30–45 s).** «Voy a seguir un concepto ficticio desde quien lo guarda hasta quien lo ve. Ana envía un peso a Bruno; el concepto persiste. Voy a comparar dos representaciones del mismo dato».

**2. Preparación (30 s).** Mostrá el reset limpio, iniciá sesión como Ana en la variante vulnerable y señalá que el payload está en la tarjeta de la guía. No leas cada carácter: menciona que el contenido está diseñado para insertar un marcador visual y no envía datos afuera.

**3. Recorrido vulnerable (60–90 s).** Enviá la transferencia, indicá que el servidor confirma el registro con HTTP 200 y observá si el marcador aparece ya en el Resumen de Ana. Cerrá sesión y recargá la página para limpiar el marcador insertado directamente en `document.body`; entrá como Bruno. El concepto puede volver a ejecutarse en su Resumen antes de abrir Actividad, porque ambas vistas usan `MovementList`. Explica que el servidor guarda el dato y la ejecución ocurre cuando el navegador lo renderiza. Si tenés DevTools abierto, muestra el nodo marcador creado en la sesión limpia de Bruno.

**4. Recorrido corregido (60–90 s).** Restablecé ambas billeteras, repetí exactamente el mismo envío en la variante corregida y volvé a entrar como Bruno. Señalá que el registro y el saldo cambiaron, el concepto se ve literal y el marcador no existe. Compara la rama de MovementList: dangerouslySetInnerHTML frente al hijo de texto React.

**5. Evidencia y cierre (45–60 s).** En Network muestra el POST 200 y el GET del historial 200 en ambas. En Elements compara DOM. Cierra con la defensa: renderizar como texto, evitar sinks HTML y usar CSP como capa adicional. El status HTTP no distingue por sí solo la seguridad del renderizado.

La duración es orientativa; se puede acortar mostrando primero el caso vulnerable, luego una captura/evidencia automática de ambos resultados. La guía conserva capturas y el resumen de la ejecución; los efectos en la base permanecen hasta el reinicio.

### Preguntas para conversación

- **¿Por qué Bruno es el observador?** Porque XSS persistente puede afectar a otra persona que consulta el dato guardado; separar emisor y receptor hace visible ese recorrido.
- **¿Por qué el envío responde 200 también en la versión segura?** Porque el backend permite guardar el concepto de prueba. La corrección demostrada cambia cómo se presenta; no depende de que la API filtre esta cadena.
- **¿Qué prueba que hubo ejecución?** El marcador DOM esperado en el recorrido vulnerable, junto con el mismo contenido confirmado en el registro. El aspecto de una cadena por sí solo no basta.
- **¿React siempre resuelve XSS?** No. En este lugar, el texto JSX representa el valor como texto. Usar dangerouslySetInnerHTML, construir atributos inseguros o colocar datos en otros contextos exige analizar esas rutas por separado.
- **¿CSP reemplaza la corrección?** No. Reduce lo que un documento puede ejecutar, pero el programa debe tratar datos no confiables como datos y evitar interpretarlos como HTML.
- **¿Qué cambiarías en producción?** Eliminar el sink HTML, usar renderizado de texto o sanitización robusta cuando haya un requisito legítimo de HTML enriquecido, revisar todas las salidas y mantener CSP estricta como defensa adicional.
