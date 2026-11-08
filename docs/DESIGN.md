# Diseño de Umbral

## Dirección visual

Umbral usa una estética de banca cotidiana: clara, serena y legible desde una pantalla proyectada. El lienzo es marfil casi blanco, las superficies son blancas, la tinta es verde grafito y el verde hoja señala acciones principales y estados confirmados. El color vive en pocos lugares; fondos y bordes suaves mantienen el foco en saldos, formularios y evidencia.

La tipografía usa una pila de sistema para evitar descargas externas y mantener el laboratorio operativo sin conexión. Los importes usan cifras tabulares. La navegación usa iconos geométricos de CSS y etiquetas visibles, sin depender de recursos remotos. Las animaciones se limitan a transiciones cortas de foco/estado y respetan `prefers-reduced-motion`.

## Billetera

La vista inicial prioriza saldo disponible y actividad reciente. La navegación cambia entre Resumen, Transferencias, Actividad, Cotizador y Administración. Las acciones privilegiadas se muestran como funciones del producto; la autorización se decide en el servidor. La variante activa se indica con una etiqueta inequívoca en el encabezado.

El formulario de transferencia separa destinatario, importe y concepto. La actividad presenta movimientos en filas simples y una búsqueda fácil de encontrar. El cotizador explica que consulta un proveedor simulado y deja visible la respuesta del servidor. El panel administrativo permite revisar usuarios y aplicar ajustes ficticios.

La misma compilación sirve a ambas variantes. `GET /api/meta` identifica la variante elegida por Flask. El aspecto permanece igual; el comportamiento de seguridad lo decide el servidor. Sólo la versión vulnerable interpreta deliberadamente el concepto de movimiento como HTML en la vista de actividad; la corregida lo representa como texto normal y tiene CSP adicional.

## Guía

La guía es un entrypoint separado con seis casos seleccionables, pasos manuales, solicitudes copiables, explicación del resultado vulnerable/corregido y descripción de la mitigación. La sección de automatización muestra estado, versión/caso en curso, resultados de cada variante y evidencia persistente. Los estados inconclusos, inesperados, cancelados y con error se distinguen visualmente; verde no se usa para sugerir éxito cuando faltan resultados.

La acción de restablecer informa que elimina los cambios de ambas billeteras e invalida sesiones. La ejecución individual deja sus efectos visibles. El lote avisa que restablecerá antes de cada caso y que las sesiones observadoras requerirán un nuevo ingreso.

## Adaptación y accesibilidad

- En pantallas amplias, la billetera usa una navegación lateral compacta y una columna principal con tarjetas de resumen y contenido.
- En móvil, la navegación se vuelve una banda desplazable y los formularios, métricas y evidencias pasan a una sola columna.
- Los controles tienen etiquetas, foco visible, estados de carga y mensajes con `role="status"` o `role="alert"` cuando corresponde.
- Los campos tienen instrucciones y errores legibles; la información nunca depende sólo del color.
- Los targets interactivos tienen tamaño y separación cómodos; las capturas conservan proporción y se pueden abrir a tamaño completo.
- Se respetan el zoom del navegador, el movimiento reducido y el orden lógico de teclado.

## Color y componentes

Los tokens están en `frontend/src/styles.css`. El verde semilla es `oklch(0.650 0.150 145)`; el sistema lo extiende con fondos claros, texto oscuro, bordes neutros, verde profundo para acción y estados separados para error, advertencia e inconcluso. Antes de cambiar un token, comprobar contraste en texto pequeño y en la proyección.

Componentes compartidos entre pantallas: marca Umbral, etiqueta de variante, botones primario/secundario, campos con etiqueta, tarjetas, alertas, chips de estado y paneles de evidencia. Mantener dimensiones y lenguaje visual iguales en las dos billeteras facilita comparar sólo el resultado de seguridad.
