# Informe técnico: seguridad en una billetera ficticia

## Propósito y alcance

El trabajo compara dos versiones locales de una billetera ficticia. Ambas permiten registrar e identificar usuarios, consultar saldo y movimientos, realizar transferencias, consultar una cotización simulada y administrar saldos. Se utilizan cuentas y dinero ficticios. La exposición presenta seis riesgos de aplicaciones web y los controles aplicados en la versión corregida.

Las dos versiones comparten el código de aplicación, el esquema de datos y la interfaz compilada. La configuración fija de cada proceso selecciona el modo `vulnerable` o `secure`; no se cambia desde una petición. Cada instancia tiene su propia base SQLite, directorio de sesiones y nombre de cookie. Los cambios intencionales están acotados al modo de enseñanza; este diseño facilita la comparación, pero exige revisar que no se active en un entorno real.

La guía coordina los ejercicios contra las mismas billeteras visibles, no contra copias. Su ejecutor utiliza solicitudes controladas y, para los casos de navegador, un navegador sin ventana propia: el estado compartido puede observarse en la aplicación del usuario. El reinicio es explícito y elimina los datos ficticios y las sesiones previas. Cada backend ofrece un canal de control independiente, autenticado y sin puerto publicado; la guía serializa las operaciones y conserva sus evidencias. El reinicio de las dos bases no es una transacción distribuida: si una operación falla, la guía debe señalar el resultado parcial y requerir un nuevo restablecimiento.

## Arquitectura y límites de confianza

```text
Navegador local → pasarela de destinos fijos (puertos sólo en loopback)
 ├── localhost:5000 → billetera vulnerable ── SQLite y sesiones A
 ├── localhost:5001 → billetera corregida  ── SQLite y sesiones B
 ├── localhost:5002 → guía y ejecutor
 └── localhost:5003 → página de demostración CSRF

Red interna Docker: ambas billeteras, guía y servicios simulados
 ├── proveedor de cotización
 └── servicio interno con información ficticia
```

La interfaz usa React, TypeScript y Vite; Flask sirve el resultado compilado junto con la API. El backend utiliza SQLite, contraseñas procesadas mediante Werkzeug y sesiones del lado del servidor con Flask-Session y CacheLib. Las transferencias representan montos en centavos enteros y agrupan débito, crédito y movimiento en una transacción. El débito condicional evita gastar un saldo insuficiente incluso ante solicitudes simultáneas.

Sólo la pasarela publica puertos del host y lo hace en loopback; conecta una red bridge de acceso con la red interna del laboratorio y reenvía a cuatro destinos fijos. Las billeteras, la guía y los servicios simulados se conectan únicamente a la red interna y no publican puertos. El acceso al control privado requiere un secreto compartido guardado fuera del código. Estas medidas reducen la exposición del laboratorio, pero una red Docker no equivale a una frontera absoluta frente a un host comprometido. El modo de enseñanza debe permanecer en una máquina y una red confiables.

En el ejercicio SSRF, incluso la versión vulnerable restringe el transporte a los dos servicios ficticios definidos por el laboratorio; no se ofrece un proxy general hacia Internet o el host. La versión corregida admite únicamente la URL fija del proveedor conocido. El nombre de dicho proveedor depende del DNS interno de Docker y de la integridad de esa red; no constituye por sí solo una solución general frente a suplantación de DNS.

## Riesgos y controles comparados

La clasificación siguiente utiliza [OWASP Top 10:2025](https://top10.owasp.org/2025/); es una taxonomía de concientización, no una certificación de seguridad.

| Riesgo | Relación con OWASP | Comportamiento de enseñanza | Control en la versión corregida |
|---|---|---|---|
| Autorización administrativa ausente | [A01: control de acceso](https://top10.owasp.org/2025/A01_2025-Broken_Access_Control/) | Un usuario autenticado puede alcanzar la operación administrativa sin tener el rol. | El servidor verifica el rol antes de listar usuarios o ajustar saldos; ocultar el panel no se considera autorización. |
| CSRF en transferencias | [A01: control de acceso](https://top10.owasp.org/2025/A01_2025-Broken_Access_Control/) | Una página de otro origen local puede inducir una transferencia con la sesión del navegador. | Un token ligado a la sesión es obligatorio en mutaciones y se comprueba `Origin` cuando está presente. La cookie `SameSite` es una defensa adicional, no reemplaza el token. |
| XSS persistente | [A05: inyección](https://top10.owasp.org/2025/A05_2025-Injection/) | El concepto almacenado se interpreta como HTML cuando otro usuario ve el movimiento. | React muestra el concepto como texto, evitando interpretarlo como marcado; una política CSP agrega protección complementaria. |
| Inyección SQL en búsqueda | [A05: inyección](https://top10.owasp.org/2025/A05_2025-Injection/) | El texto de búsqueda modifica la consulta construida dinámicamente. | El término y el identificador de usuario se transmiten como parámetros, separando los datos de la estructura de la consulta. |
| Autenticación sin limitación y enumeración | [A07: fallas de autenticación](https://top10.owasp.org/2025/A07_2025-Authentication_Failures/) | Las respuestas distinguen usuarios inexistentes y contraseñas incorrectas; no hay límite de intentos. | Se utiliza un mensaje uniforme, trabajo de hash también para usuarios inexistentes y límites locales de cinco intentos por cuenta y veinte por IP durante 60 segundos. El límite responde con `429` y `Retry-After`. |
| SSRF en consulta de cotización | [A01: control de acceso](https://top10.owasp.org/2025/A01_2025-Broken_Access_Control/) | La funcionalidad puede consultar el servicio interno ficticio desde el servidor. | La aplicación acepta sólo el proveedor fijo, sin redirecciones, con límites de conexión, lectura y tamaño, y valida el formato de la respuesta. El transporte de ambas variantes está limitado a los fixtures del laboratorio. |

La comprobación de un token CSRF no protege frente a un XSS ya ejecutado en el mismo origen: son controles para límites de confianza diferentes. Para las consultas, los parámetros protegen valores, mientras que identificadores SQL dinámicos requerirían una selección explícita; en este trabajo se usa una estructura de consulta fija.

Los controles pueden revisarse en [backend/app.py](../backend/app.py): `require_user` y `adjust` para permisos, `CSRFProtect` y `lock_request` para solicitudes entre orígenes, `movements` para consultas parametrizadas, `login` para autenticación y `quote` para la consulta al proveedor fijo. El renderizado de conceptos se compara en `MovementList`, dentro de [WalletApp.tsx](../frontend/src/wallet/WalletApp.tsx): el modo de enseñanza interpreta HTML deliberadamente y el corregido muestra texto. El [ejecutor](../lab/runner.py) mantiene separados el estado de una ejecución, sus resultados y la conservación de evidencias.

## Evidencias y resultados

La ejecución definitiva `000c0cb404874efcbacac65a876213c1`, iniciada desde la guía sobre las dos billeteras visibles, completó las doce observaciones con el comportamiento esperado. El JSON y las capturas antes/después se conservan en [la carpeta de evidencia](../evidencias/ejecucion-final/result.json). Una prueba con error de entorno, precondiciones incumplidas o tiempo agotado se marca como inconclusa; los intentos anteriores se conservaron con sus estados reales.

| Caso | Evidencia esperada en vulnerable | Resultado | Evidencia esperada en corregida | Resultado |
|---|---|---|---|---|
| Autorización administrativa | Usuario sin rol cambia un saldo ficticio. | Reproducido | Respuesta de acceso denegado y saldo sin cambios. | Verificado |
| CSRF | Formulario del origen de demostración produce una transferencia. | Reproducido | Solicitud rechazada y ningún movimiento nuevo. | Verificado |
| XSS persistente | Un marcador inocuo se activa en el navegador de la cuenta receptora. | Reproducido | El concepto se muestra como texto y el marcador no se activa. | Verificado |
| Inyección SQL | La búsqueda devuelve un conjunto alterado respecto del filtro normal. | Reproducido | El texto se trata como dato y no amplía el acceso. | Verificado |
| Autenticación | Respuestas distintas y ausencia de limitación en el umbral del ejercicio. | Reproducido | Respuesta uniforme y limitación verificable. | Verificado |
| SSRF | La consulta devuelve el marcador del servicio interno ficticio. | Reproducido | El destino interno se rechaza y el servicio no recibe la consulta. | Verificado |

Se aprobaron 21 pruebas de backend, guía y pasarela con el entorno Python actualizado, incluidas concurrencia, invalidación de sesiones, reinicio parcial, cancelación, timeout de un proceso real y rechazo de un importe de formulario con 5000 dígitos. La interfaz compiló con comprobación de tipos. La revisión en Chromium cubrió 22 combinaciones de pantalla/tamaño a 1440 px y 390 px, ocho comprobaciones de foco visible y ausencia de errores JavaScript no controlados. Su [reporte visual](../evidencias/visual/report.json) distingue los 401 esperados al cargar una sesión anónima y el error de login simulado exclusivamente para revisar esa vista; el lote de seguridad utiliza peticiones reales.

En una billetera abierta se observó el cambio de 100000 a 105000 centavos sin recargar. El restablecimiento recuperó los saldos, invalidó esa sesión y preservó los informes. La cancelación iniciada desde la guía (`8765110ce3bb4dc2ab39258d3058b2b3`) terminó como cancelada/inconclusa y no dejó procesos Chromium. Se ensayó un arranque completo con `--no-build --pull never --wait`; el ejecutor sólo tiene la red interna y no dispone de una ruta de salida por defecto. La pasarela mantiene publicados exclusivamente los cuatro puertos locales.

Se auditó el archivo de versiones Python fijadas con `pip-audit 2.10.1`. Inicialmente se identificaron avisos en Flask, pytest y requests; se actualizaron a las versiones corregidas 3.1.3, 9.0.3 y 2.33.0, respectivamente. Una segunda auditoría del archivo actualizado no encontró vulnerabilidades conocidas en las versiones consultadas. El archivo fija versiones, pero no incorpora hashes de paquetes. Este análisis no cubrió paquetes del sistema operativo, la imagen base ni Chromium, y su resultado depende de los avisos disponibles al momento de la consulta.

## Limitaciones

- El proyecto utiliza HTTP local para simplificar la exposición. La cookie de sesión se configura con `HttpOnly` y `SameSite=Lax`, pero sin `Secure` para esta ejecución HTTP. En una implementación real se requiere HTTPS y la bandera `Secure`; aquí no se ofrece confidencialidad de transporte.
- Las credenciales y saldos iniciales son públicos y ficticios. No hay identidad real, integración bancaria, cumplimiento normativo, recuperación de cuenta ni garantías financieras.
- La caché de sesiones usa almacenamiento local privado. El serializador predeterminado de `FileSystemCache` emplea pickle: ese directorio no debe ser modificable por usuarios o contenido no confiable.
- El candado de mantenimiento está diseñado para un único proceso por instancia. Los límites de inicio de sesión y el estado de sesiones son locales; no representan una arquitectura distribuida.
- Las imágenes y Chromium deben construirse y descargarse con anticipación. La ejecución sin conexión requiere que esas imágenes ya estén disponibles y haya sido comprobada.
- Las pruebas son demostraciones acotadas; no constituyen una auditoría integral, una evaluación de penetración ni una garantía de ausencia de defectos.

## Fuentes

- [OWASP Top 10:2025](https://top10.owasp.org/2025/) y sus categorías [A01](https://top10.owasp.org/2025/A01_2025-Broken_Access_Control/), [A05](https://top10.owasp.org/2025/A05_2025-Injection/) y [A07](https://top10.owasp.org/2025/A07_2025-Authentication_Failures/).
- [OWASP: prevención de CSRF](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html), [inyección SQL](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html) y [SSRF](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html).
- [Documentación de sesiones Flask-Session](https://flask-session.readthedocs.io/en/latest/usage.html), [serialización de CacheLib](https://cachelib.readthedocs.io/en/stable/api/serializers/) y [transacciones SQLite](https://www.sqlite.org/lang_transaction.html).
