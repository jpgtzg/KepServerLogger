# Brooksville: piloto de logs JSON

## Antes del despliegue

Confirmar el contexto/host, namespace, Deployment y contenedor reales de
Brooksville, arquitectura de los nodos y servidores atendidos por ese ingestor.
No aplicar los manifiestos de ejemplo del repositorio: contienen referencias a
Balcones. Si el Deployment atiende otras plantas, acordar ese alcance antes de
reemplazar la imagen.

Guardar la referencia y disponibilidad de la imagen anterior y la configuración
del Deployment para rollback, sin exportar Secrets. Comprobar que la estrategia
evite dos ingestors concurrentes (el ejemplo del repo usa Recreate). El reemplazo
implica una breve pausa de adquisición.

## Imagen de prueba

Con Docker activo, construir desde la raíz. Para nodos Linux amd64:

```sh
docker build --platform linux/amd64 -f ingestor/Dockerfile -t ingestor:release2-json-pilot .
docker save -o /tmp/ingestor-release2-json-pilot.tar ingestor:release2-json-pilot
```

Usar un tag nuevo por cada build posterior. Transferir e importar la imagen en
los nodos donde pueda programarse el pod, o usar el registro aprobado. Reemplazar
solo la imagen del contenedor existente mediante el procedimiento del clúster;
conservar configuración, certificados, credenciales y volúmenes actuales.
No levantar un ingestor adicional ni recrear TimescaleDB.

## Evidencia de 15–30 minutos

1. Confirmar arranque y que TimescaleDB siga recibiendo muestras.
2. Capturar logs del contenedor ingestor sin `--timestamps`. Registrar pod,
   imagen, inicio/fin de captura y reinicios.
3. Validar que cada línea de aplicación sea JSON. Los mensajes de arranque del
   entrypoint u otros procesos deben identificarse por separado.
4. Revisar `telemetry.cpu`, `telemetry.ram` y `telemetry.storage` para cada servidor
   configurado. Una métrica deshabilitada no debe considerarse pérdida.
5. Comparar muestras por `server_name`/`database` y `data.timestamp` contra las
   tablas locales. Usar el timestamp de origen, no el timestamp del log.
6. Medir bytes y registros por duración real de captura; extrapolar a un día
   solo si la ventana es representativa. Separar mediciones y mensajes operativos.

Consultas de lectura sobre la base del servidor correspondiente:

```sql
SELECT timestamp, usage FROM cpu_usage ORDER BY timestamp DESC LIMIT 20;
SELECT timestamp, total_kb, free_kb FROM ram_usage ORDER BY timestamp DESC LIMIT 20;
SELECT timestamp, free_gb, used_gb, total_gb
FROM storage_usage ORDER BY timestamp DESC LIMIT 20;
```

La columna REAL puede redondear ligeramente los valores JSON; comparar con
tolerancia numérica. RAM está expresada en KiB y disco en GiB aunque sus nombres
de campo terminen en `_kb`/`_gb`.

## Aceptación y rollback

Aceptar cuando las mediciones coincidan, los servidores no mezclen contexto y
la adquisición local continúe sin una regresión atribuible al cambio. Registrar
los errores conocidos de la prueba como línea base. Si hay regresión, restaurar
la imagen anterior y confirmar recuperación; no cambiar esquema ni borrar datos.

Esta prueba valida generación local de telemetría; la recepción en Log Analytics
se verificará después con los permisos correspondientes. No acredita replay ni
entrega garantizada a la nube.
