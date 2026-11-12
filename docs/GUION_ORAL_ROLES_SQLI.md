# Guion oral: roles e inyección SQL

Texto entre comillas: lo que decimos. Las acciones entre corchetes no se leen. Cada tema contiene unos 90–110 segundos de habla, según el ritmo; con clics, pausas y latencia puede llevar 2:15–2:30 o más. Si la respuesta tarda, no presentar un resultado no observado como exitoso.

## Preparación, fuera del cronómetro

Las demostraciones son independientes: las transferencias de SQLi cambiarían el saldo inicial que usamos en roles. Si exponemos roles primero, hay que restablecer y preparar las dos transferencias en cada variante **entre temas**: es una pausa real fuera de los tiempos de cada caso, que puede llevar varios minutos. Un compañero puede ayudar con esa preparación. Alternativamente, preparar SQLi antes de empezar, exponerlo primero y luego restablecer ambas instancias e iniciar sesión como Ana para roles; ensayar esa transición. Las dos partes suman unos cuatro minutos de habla, más acciones, cambios de cuenta, reinicio y latencia; no se garantizan cuatro minutos de presentación total.

- Usar sólo las instancias locales autorizadas: vulnerable `localhost:5000` y corregida `localhost:5001`, siempre con `localhost`. Tras restablecer, volver a ingresar: las sesiones anteriores se invalidan.
- Para roles, comprobar primero desde la interfaz que `admin` puede ajustar y revertir un ajuste; luego restablecer para recuperar saldo de Ana de 100000 centavos. En cada variante entrar como `ana`, verificar `/api/me`, abrir F12 y dejar copiado el script de [estudio](EXPLICACION_ESTUDIO_ROLES_SQLI.md). Mostrar en Sources el código compartido buscando `/api/admin`, o haber observado esa ruta en Network durante el control autorizado de admin. Ana no ve Administración. Tener abiertas las líneas de la tabla y capturas de respaldo. Ejecutar una sola vez el POST exitoso: vuelve a sumar si se repite.
- Para SQLi, después de terminar roles y restablecer, preparar **en cada variante**: Ana transfiere $1 a Bruno con concepto `Compra propia`; salir, entrar como admin y transferir $1 a Bruno con concepto `Movimiento reservado`; salir y volver como Ana. En Actividad comprobar que aparece la propia, no la reservada. Tener F12 → Network/Red, filtro `movements`, búsqueda de prueba copiada y código abierto. Una búsqueda normal `Compra propia` debe funcionar.
- Indicio opcional antes de exponer: buscar una comilla sola en Actividad muestra un error de SQLite en vulnerable; en corregida se busca como texto. El error no demuestra por sí solo acceso a filas ajenas.

## Roles: exposición

| Tiempo orientativo | Acción y texto |
| --- | --- |
| 0:00–0:30 | [Mostrar Ana y `/api/me`; señalar ausencia de Administración y ruta descubierta en Sources o Network.] «Ana inició sesión, así que sabemos quién es, pero su rol es usuario. La interfaz no le muestra Administración. Sin embargo, esconder un botón no impide enviar una solicitud a la función que existe en el servidor. La pregunta es si el servidor controla quién puede usarla.» |
| 0:30–1:05 | [Ejecutar el script una vez en vulnerable; mostrar respuesta y saldo.] «La solicitud usa la sesión de Ana, obtiene su identificador y un token válido, y pide sumar cincuenta pesos. En la versión vulnerable recibimos 200 y el saldo pasa de 100000 a 105000 centavos. La operación administrativa se ejecutó aunque Ana no tiene ese permiso.» |
| 1:05–1:40 | [Abrir `adjust` y `require_user`; señalar condición.] «En el código, ajustar exige `admin=True`. El selector elige primero la variante: la vulnerable devuelve al usuario sin comprobar su rol. En la rama corregida, si se exige administración y el rol no es administrador, responde 403 antes de cambiar el saldo.» |
| 1:40–2:15+ | [Ejecutar en corregida; mostrar 403 y saldo intacto.] «Con la misma cuenta y un token válido, la corregida rechaza a Ana y conserva los 100000 centavos. Antes verificamos que un administrador legítimo sí puede hacer y revertir un ajuste. El token atiende otra protección; no concede privilegios. La regla de autorización tiene que aplicarse en el servidor.» |

## SQLi: exposición

| Tiempo orientativo | Acción y texto |
| --- | --- |
| 0:00–0:30 | [Mostrar Actividad de Ana y las dos filas preparadas en las notas; buscar `Compra propia`.] «Ana entra normalmente y sólo debería ver movimientos donde participa. Preparamos una transferencia propia a Bruno y otra entre admin y Bruno. La búsqueda normal encuentra la propia; la reservada es ajena a Ana. En Red observamos que la pantalla envía el término al servidor.» |
| 0:30–1:05 | [Buscar `' OR 1=1 --` en vulnerable; mostrar fila reservada y Response.] «Al buscar esta cadena en la vulnerable aparece también el movimiento reservado. La respuesta es 200, pero la evidencia de la falla es la fila ajena, cuya procedencia conocemos. La búsqueda se convirtió en parte de la consulta SQL y alteró la condición que limitaba los resultados.» |
| 1:05–1:40 | [Mostrar las ramas de `movements`.] «Acá la versión vulnerable intercala directamente el texto en la sentencia. La comilla cierra el texto esperado, `OR 1=1` agrega una condición verdadera y los guiones comentan lo que sigue. En la corregida la sentencia usa signos de pregunta y entrega los valores por separado; además conserva el filtro por propietario.» |
| 1:40–2:15+ | [Repetir en corregida y mostrar Response; buscar `Compra propia`.] «En la corregida la misma búsqueda responde 200 pero no devuelve la fila reservada; la búsqueda propia sigue funcionando. No evitamos el inicio de sesión ni borramos datos: demostramos que una consulta posterior expuso una fila ajena. El contraste depende de mirar el contenido, no sólo el código HTTP.» |

## Código listo para mostrar

| Tema | Punto y ruta portable | Qué señalar |
| --- | --- | --- |
| Roles | [backend/app.py:310](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:310>), `adjust` | `require_user(admin=True)` antes del cambio. |
| Roles | [backend/app.py:176](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:176>), `require_user` | Selección de rama y control de rol con 403. |
| SQLi | [backend/app.py:273](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:273>), `movements` | `q` interpolado en la sentencia vulnerable. |
| SQLi | [backend/app.py:277](<C:/Users/jonat/Documents/ChatGPT/Seguridad en el Desarrollo de Software/tpi-billetera/backend/app.py:277>), `movements` | Consulta fija, parámetros y filtro de propiedad. |

**Ampliación opcional, unos 30 segundos:** «En la consulta original, `AND` se evalúa antes de `OR`, de modo que la condición verdadera se aplica por fuera de la restricción de propiedad. Los parámetros impiden que la entrada agregue sintaxis, pero igual necesitamos conservar el filtro que decide qué filas le corresponden a Ana.»
