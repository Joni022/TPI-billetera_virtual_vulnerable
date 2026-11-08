# Umbral · laboratorio local de seguridad

Umbral es una billetera ficticia para comparar seis fallas de seguridad con su comportamiento corregido. Todo el estado, las cuentas y los servicios de cotización son de demostración y viven dentro del laboratorio local.

## Inicio rápido

Requisitos: Docker Desktop con Docker Compose y puertos locales 5000–5003 disponibles. Desde esta carpeta:

```powershell
docker compose up --build
```

Cuando los servicios indiquen que están listos, abrí:

- Guía y pruebas: <http://localhost:5002>
- Billetera vulnerable: <http://localhost:5000>
- Billetera corregida: <http://localhost:5001>

La página atacante CSRF local está en <http://localhost:5003> y se usa desde el ejercicio correspondiente. Los servicios sólo se publican en loopback. Para detenerlos, usá `Ctrl+C`; para apagarlos después, `docker compose down`.

La primera instalación descarga imágenes y dependencias. Luego el laboratorio funciona localmente sin consultar servicios externos: las cotizaciones y el servicio interno son fixtures ficticios en la red privada de Docker.

## Cuentas de demostración

| Usuario | Contraseña | Rol |
| --- | --- | --- |
| `ana` | `Demo1234!` | Usuario |
| `bruno` | `Demo1234!` | Usuario |
| `admin` | `Demo1234!` | Administrador |

Cada billetera empieza con datos separados y $1.000,00 por cuenta. Restablecer desde la guía devuelve los datos semilla e invalida las sesiones de ambas variantes. Volvé a iniciar sesión en las billeteras que estés observando. Las capturas y los resultados del laboratorio se conservan aparte.

## Uso de la guía

La guía documenta los seis ejercicios manuales y automáticos. Para una prueba individual, restablecé ambas billeteras, iniciá sesión en ellas con cuentas demo y ejecutá el caso desde la guía. La automatización usa sesiones propias y trabaja sobre esas mismas instancias visibles; no toma las cookies del navegador humano. Los cambios reales de la prueba permanecen en pantalla hasta el siguiente reinicio.

El lote **Ejecutar los seis** pide una confirmación antes de comenzar. Restablece ambas variantes antes de cada caso y guarda doce resultados secuenciales, dos por ejercicio. Los reinicios cierran las sesiones humanas, por lo que habrá que volver a ingresar para observar las pantallas. Si se cancela una ejecución, se vence el tiempo o hay un fallo parcial, el resultado queda marcado como cancelado, inconcluso o error; no se declara éxito automáticamente.

Cada resultado puede incluir solicitud/respuesta resumida, estado anterior y posterior, y capturas. La evidencia no debe contener cookies ni tokens CSRF. La guía conserva los últimos diez trabajos; un reinicio de datos no borra sus capturas.

## Desarrollo local del frontend

Para trabajar sólo en la interfaz, con Node.js 22 o posterior:

```powershell
cd frontend
npm ci
npm run dev
```

El wallet se abre en <http://127.0.0.1:5173/> y la guía en <http://127.0.0.1:5173/guide.html>. Vite reenvía `/lab/api` y `/lab/artifacts` a la guía local en el puerto 5002, y `/api` a la billetera vulnerable por defecto. Para trabajar contra la corregida, fijá `VITE_API_TARGET` antes de iniciar Vite:

```powershell
$env:VITE_API_TARGET = "http://localhost:5001"
npm run dev
```

Las rutas proxy requieren levantar el laboratorio completo. Los servicios Flask sirven el mismo `frontend/dist`; la variante la declara cada servidor. Para verificar el frontend:

```powershell
npm run typecheck
npm run build
```

Las pruebas de navegador CSRF y XSS se implementan en `tests_browser/scenarios.py` y se ejecutan desde el runner del laboratorio, no desde la interfaz cliente.

## Estructura

- `frontend/`: React, TypeScript y CSS propio para billetera y guía.
- `backend/`: API Flask de las dos variantes.
- `lab/`: control local, restablecimiento y runner de casos automáticos.
- `tests_browser/`: escenarios reales de navegador para CSRF y XSS persistente.
- `fixtures/`: proveedor de cotizaciones y servicio interno ficticios.
- `docs/GUIA.md`: procedimientos manuales, solicitudes y controles.
- `docs/DESIGN.md`: dirección visual y reglas de interfaz.
- `docs/API.md`: contrato de integración de las APIs.
- `docs/SEGURIDAD.md`: límites y notas técnicas del laboratorio.

Este proyecto es una práctica académica local, no un producto financiero ni una guía para atacar sistemas ajenos.
