# Guion oral: presentación de Umbral y XSS

El texto entre comillas está pensado para leer en voz alta. Las acciones entre corchetes son indicaciones y no se leen. Los tiempos son orientativos: los clics, la latencia y los cambios de ventana pueden extender la exposición. Si una acción falla, no presentar el resultado esperado como si se hubiera observado.

## Preparación, fuera del cronómetro

- Iniciar los servicios según el [README](../README.md). Usar siempre `localhost`: vulnerable en [puerto 5000](http://localhost:5000), corregida en [5001](http://localhost:5001) y guía en [5002](http://localhost:5002). La página auxiliar del puerto 5003 corresponde a CSRF y no se usa en esta prueba.
- Si una demostración anterior alteró los datos, restablecer ambas versiones al **comienzo de XSS** desde la guía y comprobar que el reinicio terminó en ambas. El reset revoca las sesiones: recargar y volver a ingresar. No restablecer entre el envío de Ana y la visualización de Bruno ni entre variantes durante este recorrido.
- Preparar dos perfiles o contextos de navegador independientes, uno para Ana y otro para Bruno. En cada perfil ingresar a ambas variantes con la cuenta correspondiente: `ana` o `bruno`, contraseña `Demo1234!`. Las bases y las cookies de las variantes están separadas, pero dos pestañas de una misma variante y perfil comparten sesión. Como alternativa, cerrar sesión de Ana, **recargar** y entrar como Bruno en cada variante: el marcador insertado en el documento puede quedar visible después del cierre de sesión de la aplicación.
- Comprobar los saldos iniciales. Con datos recién restablecidos, Bruno tiene 100000 centavos ($1.000); recibirá 100 centavos ($1) en cada variante. No ejecutar simultáneamente el caso automático y la demostración manual: comparten bases de datos.
- Tener abierto el concepto de la guía, las ventanas de Ana y Bruno y el código de la tabla inferior. El ejemplo agrega un marcador visual; no envía cookies ni contraseñas. Copiar los **189 caracteres exactos** del siguiente bloque como texto en el campo Concepto, sin ejecutarlo en la guía ni en este documento:

```html
<img src=x onerror="document.body.insertAdjacentHTML('afterbegin','<div data-testid=&quot;xss-marker&quot; style=&quot;color:red;font-weight:bold&quot;>XSS ejecutado</div>');this.remove()">
```

## Presentación general: 30–45 segundos

| Tiempo orientativo | Acción y texto |
| --- | --- |
| 0:00–0:45 | [Mostrar la pantalla de Umbral y la guía.] «Presentamos Umbral, una billetera ficticia para nuestro trabajo práctico de Seguridad en el Desarrollo de Software. Usamos cuentas y dinero ficticios para comparar vulnerabilidades con defensas. La aplicación combina Python y Flask, SQLite, React y TypeScript. El mismo código funciona en dos modos definidos al arrancar, con datos y sesiones separados: uno vulnerable y otro corregido para los escenarios demostrados. Realizamos pruebas manuales y automáticas; la guía conserva evidencias y permite restablecer los datos. Ahora mostraremos XSS persistente; luego continuaremos con autorización por roles e inyección SQL.» |

Para una lámina, los seis casos son: autorización por roles, inyección SQL, XSS persistente, CSRF, autenticación y SSRF. El puerto 5003 es una página auxiliar para el caso CSRF.

## XSS: exposición de 2:15–2:30 aproximadamente

El texto tiene cerca de 90–110 segundos de habla; el resto del tiempo contempla acciones y pausas. Ensayar la secuencia completa: la duración real depende del ritmo y del sistema.

| Tiempo orientativo | Acción y texto |
| --- | --- |
| 0:00–0:30 | [En vulnerable, como Ana, abrir **Transferencias**. Elegir `bruno`, ingresar `1` y pegar el concepto; pulsar **Enviar transferencia**.] «XSS ocurre cuando una entrada termina ejecutando código en el navegador de quien visita una página. Este caso es persistente porque el concepto queda guardado. Ana transfiere un peso a Bruno y coloca un ejemplo que genera un marcador visual inocuo.» |
| 0:30–1:00 | [Confirmar el envío; abrir el perfil limpio de Bruno en la misma variante y mostrar **Actividad**. El marcador puede aparecer ya en Resumen, en Actividad reciente.] «La transferencia se completa y el servidor guarda el concepto. Cuando Bruno consulta sus movimientos, el navegador interpreta ese contenido como HTML y ejecuta el evento de la imagen: aparece “XSS ejecutado”. El efecto ocurre al mostrar el dato, no al guardarlo.» |
| 1:00–1:35 | [Mostrar `MovementList` y señalar ambas ramas; mostrar el INSERT.] «En el código compartido, la versión vulnerable usa dangerouslySetInnerHTML para insertar el concepto como HTML. La corregida lo muestra como texto con React. La consulta que guarda la transferencia usa parámetros: eso evita confundir este caso con inyección SQL, pero no corrige por sí solo la salida HTML.» |
| 1:35–2:30 | [Repetir el envío en la corregida y abrir Actividad como Bruno. Mostrar el concepto literal y la transferencia; volver a Resumen para mostrar el saldo.] «En la corregida enviamos exactamente el mismo concepto. La transferencia legítima también se completa y Bruno recibe el peso, pero el contenido aparece como texto y no se crea el marcador. Además, una política CSP agrega otra capa de defensa. Comparamos el efecto observado y el funcionamiento normal: este resultado corresponde al escenario probado.» |

## Código para mostrar

| Ubicación | Qué señalar |
| --- | --- |
| [backend/app.py:288](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:288>) | Valida el concepto y limita su longitud a 200 caracteres. |
| [backend/app.py:299](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:299>) | Inserta la transferencia con parámetros, incluido el concepto. |
| [WalletApp.tsx:752](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/frontend/src/wallet/WalletApp.tsx:752>) | Rama vulnerable con `dangerouslySetInnerHTML` y rama corregida que representa texto. |
| [backend/app.py:145](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:145>) | Cabecera CSP como protección adicional en la variante corregida. |
| [tests_browser/scenarios.py:20](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/tests_browser/scenarios.py:20>) | Valor exacto del concepto usado por el escenario automático. |

## Si algo falla y respaldo

- Sin marcador en vulnerable: confirmar que el concepto se copió completo, que la transferencia se completó y que Bruno mira la misma variante. Si faltan datos, el ensayo es inconcluso.
- Si no aparece el movimiento, comprobar destinatario, sesión, saldo y respuesta del envío. Si hubo un reset entre el envío y la lectura, volver a preparar el caso desde el comienzo.
- Si aparece un marcador antes de entrar como Bruno, puede provenir de Ana: usar el perfil independiente o cerrar sesión y recargar antes de entrar. Resumen también puede activar el ejemplo; Actividad facilita observar el movimiento.
- Si falla el ensayo en vivo, mostrar como evidencia histórica las capturas [vulnerable después](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/output/playwright/guide-review-compact/xss-vulnerable-after.png>) y [corregida después](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/output/playwright/guide-review-compact/xss-secure-after.png>) y explicar que son de una ejecución anterior, no del intento fallido.

## Para responder preguntas

- **¿Por qué persistente?** El servidor guarda el concepto y otra persona puede encontrarlo después. En el reflejado, la entrada regresa en la respuesta sin necesitar ese almacenamiento persistente.
- **¿HTML ya significa XSS?** No necesariamente. En este ejemplo, el HTML incluye un evento que ejecuta JavaScript y crea un marcador; verlo como texto no lo ejecuta.
- **¿La CSP alcanza sola?** Es una capa adicional. La corrección principal mostrada es representar este concepto no confiable como texto; la prueba combinada no mide cada defensa por separado.

Para ampliar el recorrido, consultar la [guía detallada de roles, SQLi y XSS](GUIA_EXPOSICION_ROLES_SQLI_XSS.md).
