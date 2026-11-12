# Instrucciones de Billetera Umbral

Alcance: esta carpeta y sus subcarpetas.

## Al retomar

Leer [docs/CONTEXTO_PROYECTO.md](docs/CONTEXTO_PROYECTO.md) al iniciar un chat nuevo, recibir un traspaso o necesitar las decisiones y pendientes. Es el contexto persistente principal. Leer [README.md](README.md) para arrancar y comprobar el estado real antes de cambiar código. El documento distingue verificaciones históricas de comprobaciones nuevas.

## Mapa y contratos

| Área | Ruta | Responsabilidad |
| --- | --- | --- |
| API Python | backend/ | Billeteras vulnerable/corregida, persistencia, sesiones y pasarela. |
| Interfaz React/TypeScript | frontend/ | Componentes de billetera, guía y diseño compartidos. |
| Coordinador | lab/ | Reinicio interno autenticado, pruebas, cancelación y evidencia. |
| Navegador | tests_browser/ | Escenarios Chromium y revisión visual. |
| Simulaciones | fixtures/ | Cotizador y servicio interno ficticios. |
| Pruebas | tests/ | Backend, coordinador y pasarela. |

Las billeteras sirven el mismo frontend y usan /api; la guía usa /lab/api. Contratos en [docs/API.md](docs/API.md). Mantener separados modo, datos y sesiones. Conservar la contención local, el canal de control privado y los fixtures acotados cuando se modifiquen los ejercicios.

## Documentación y validación

Para consultas de exposición sobre autorización, SQLi o XSS, usar [la guía detallada](docs/GUIA_EXPOSICION_ROLES_SQLI_XSS.md). Para los seis ejercicios, consultar docs/GUIA_EXPLICADA.md y docs/GUIA.md. Verificar funciones y líneas actuales antes de citarlas; las exportaciones PDF/DOCX generales preceden a la guía de tres temas.

Desde esta carpeta, con entornos preparados: backend/coordinador con .\.venv\Scripts\python.exe -m pytest tests -q --basetemp .test-tmp-local; frontend desde frontend/ con npm run typecheck y npm run build. Arranque Docker y revisión visual en README. Ejecutar las comprobaciones pertinentes a los cambios y registrar lo efectivamente verificado.

## Continuidad

Mantener actualizado el contexto después de cambios importantes. Hablar en español claro y respetar la preferencia de orquestación y delegación a Terra con esfuerzo High descrita en ese archivo. El pendiente conocido de liberación del candado ante fallos de almacenamiento del runner se documenta allí; confirmar su estado antes de darlo por resuelto.
