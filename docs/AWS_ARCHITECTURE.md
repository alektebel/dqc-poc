# Qué construiríamos en AWS

Objetivo acordado: **tiempo de pared** con catálogos grandes de controles,
**aislamiento de fallos** por regla y **coste bajo en uso esporádico**. La
tabla a revisar **ya vive en la base de datos del banco**: no se sube.

Este documento describe lo que se desplegaría. Nada de ello está
desplegado ni probado contra AWS; lo que sí está hecho y probado es el
refactor del backend que lo hace posible (ver "Qué ya está listo").

---

## 1. La corrección más importante a la propuesta

La propuesta decía "una serie de lambdas para procesar cada control por
separado". Hay dos lecturas y solo una es buena:

| Lectura | Veredicto |
|---|---|
| Una **función** Lambda distinta por tipo de control (completitud, rango, consistencia…) | **No.** El código es idéntico para todos: mismo prompt, mismo bucle, misma validación. Serían N artefactos que desplegar, versionar y monitorizar para ejecutar el mismo binario. El tipo de control es un dato, no una topología. |
| Una **invocación** por regla, sobre una única función | **Sí.** Es el fan-out real: paralelismo, aislamiento y reintento por regla, con un artefacto que desplegar. |

Todo lo que sigue asume la segunda.

---

## 2. Arquitectura

```
Navegador
   │
   ├── S3 + CloudFront ─────────── las 4 pantallas (HTML/JS estático)
   │
   └── API Gateway (HTTP API) ──── Lambda "api"  (FastAPI vía Mangum)
                                        │
                                        ├── DynamoDB ── revisiones, controles, jobs
                                        ├── S3 ──────── diccionarios subidos
                                        └── Step Functions (Standard)
                                                  │
                                                  └── Map (maxConcurrency=N)
                                                        └── Lambda "rule-worker" × N reglas
                                                              ├── Bedrock  (vía VPC endpoint)
                                                              └── BBDD del banco (VPC + DX/VPN)
```

**El flujo de un lote**: la API crea el job y sus filas en DynamoDB,
arranca una ejecución de Step Functions y devuelve `job_id` (202). El
`Map` invoca una Lambda por regla. Cada worker escribe su propia fila al
terminar. La pantalla hace *polling* de `GET .../jobs/{job_id}`, que es
una sola `Query` a DynamoDB.

### Por qué cada pieza

**Step Functions Standard, no Express.** Express tiene un tope de 5
minutos por ejecución; un lote de 100 reglas a 2-3 minutos cada una no
cabe aunque vayan en paralelo. Standard llega a un año y cobra por
transición de estado, que a este volumen es ruido.

**`Map` con `maxConcurrency` explícito.** El límite no es Lambda: son las
cuotas de Bedrock (peticiones y tokens por minuto) y, sobre todo, **las
conexiones a la base de datos del banco**. Lanzar 100 workers contra un
Oracle de producción no es una optimización, es un incidente. Empezaría
con `maxConcurrency: 5` y lo subiría con medidas, no con optimismo.

**Reintentos en el estado, no en el código.** `Retry` de Step Functions
con `BackoffRate` para `ThrottlingException` de Bedrock y errores
transitorios de red; `Catch` para marcar la fila como error sin tumbar el
`Map` (`ToleratedFailurePercentage`).

**DynamoDB, tabla única.** Todo lo de una revisión se lee con una Query:

| `pk` | `sk` | Qué es |
|---|---|---|
| `REV#<id>` | `META` | la revisión |
| `REV#<id>` | `CHECK#<check_id>` | un control generado |
| `REV#<id>` | `JOB#<job_id>` | la cabecera del lote |
| `REV#<id>` | `JOB#<job_id>#ITEM#<idx>` | una regla del lote |

On-demand: en uso esporádico se paga por operación y en reposo es cero.

**La API en Lambda (Mangum), no en Fargate.** Con uso esporádico, Fargate
cobra 24/7 por un contenedor que está ocioso. El precio es un arranque en
frío de 1-3 s en la primera petición, que con este patrón de uso será casi
siempre. Si molesta: `provisioned concurrency` (coste fijo) o aceptarlo.

---

## 3. La red es lo caro, no el cómputo

El worker necesita llegar a dos sitios: **Bedrock** y **la base de datos
del banco**. Lo segundo obliga a meterlo en una VPC (subred privada +
Direct Connect o VPN hacia el banco). Y una Lambda en subred privada no
tiene salida a internet.

Dos formas de resolverlo, con costes muy distintos:

| Opción | Coste fijo aproximado | Comentario |
|---|---|---|
| NAT Gateway | **~33 $/mes** + tráfico | Se paga esté o no ejecutándose |
| VPC endpoints de interfaz (Bedrock, Secrets Manager, Logs) | **~8 $/mes cada uno** | S3 y DynamoDB van por gateway endpoint, que es gratis |

**Este es el hallazgo de coste que contradice en parte el objetivo.** El
cómputo de un lote de 100 reglas cuesta céntimos; la red cuesta entre 25
y 35 $/mes **haya o no ejecuciones**. Con tres endpoints de interfaz en
vez de NAT rondaríamos los 24 $/mes, y no bajaría de ahí mientras el
entorno exista. Sigue siendo mucho menos que un ECS permanente, pero "casi
cero" no es.

**Credenciales de la base de datos**: Secrets Manager (0,40 $/secreto/mes),
con rotación, y una cuenta **de solo lectura** sobre un esquema de
lectura. El backend además rechaza cualquier consulta que no sea un SELECT
antes de mandarla (`assert_read_only`), pero eso es la segunda línea de
defensa, no la primera.

---

## 4. Costes, en órdenes de magnitud

Para un lote de **100 reglas**, en `eu-west-1`. Los precios unitarios
deben confirmarse en la calculadora de AWS antes de ponerlos en una
propuesta: cambian, y varios dependen del modelo elegido.

| Concepto | Cálculo | Aproximado |
|---|---|---|
| Lambda worker | 100 × 1024 MB × ~180 s | ~0,30 $ |
| Step Functions Standard | ~500 transiciones | ~0,01 $ |
| DynamoDB on-demand | unos miles de operaciones | céntimos |
| API Gateway + S3 + CloudFront | polling incluido | céntimos |
| **Bedrock** | 4-6 llamadas/regla | **depende del modelo** |

El coste del lote lo decide **el modelo**, no la infraestructura. Con un
modelo pequeño tipo Nova Micro el lote entero se queda en el entorno de
unos céntimos; con un modelo grande sube dos órdenes de magnitud. Esa es
la palanca a mover si el coste preocupa, no la arquitectura.

Y la comparación honesta: **un lote de 100 reglas en un contenedor con 8
hilos cuesta lo mismo en Bedrock y ~0 € en cómputo.** El fan-out compra
tiempo de pared y aislamiento, no ahorro.

---

## 5. Presupuesto de tiempo

| Paso | Llamadas al modelo | Peor caso |
|---|---|---|
| Suficiencia | 1 | 1 × timeout |
| Generación + corrección | hasta 3 | 3 × timeout |
| Explicación | 1 | 1 × timeout |

Con `REGLLM_LLM_TIMEOUT=120` el peor caso son ~10 minutos, contra los 15
de techo de Lambda. **Recomendación: bajar el timeout a 45-60 s en el
worker** y dejar que el reintento de Step Functions absorba una llamada
lenta, en vez de gastar el presupuesto entero en un intento colgado.

---

## 6. Qué ya está listo (y probado en local)

El refactor hecho en este commit deja el backend con la forma que esta
arquitectura necesita, sin depender de AWS para nada:

| Pieza | Fichero | Para qué sirve en AWS |
|---|---|---|
| Bucle de agente sin FastAPI | `api/dq/pipeline.py` | el cuerpo de la Lambda worker; el LLM y el ejecutor entran por parámetro |
| Unidad de trabajo | `api/dq/worker.py` | `run_rule(...)` → dict JSON: exactamente la entrada y la salida de una invocación |
| Dónde corre la consulta | `api/dq/executor.py` | `DatabaseExecutor` sobre DB-API 2.0 = la conexión al motor del banco; `assert_read_only` la protege |
| Jobs con fila por regla | `training/dq/jobs_db.py` | el mismo modelo que las filas de DynamoDB que escribiría el `Map` |
| Fan-out local | `revisions.py` (`ThreadPoolExecutor`) | el equivalente del `Map`: un worker por regla, cada uno **con su propio acceso a los datos** |
| Polling | `GET .../jobs/{job_id}` | el contrato de la pantalla ya no depende de mantener una conexión abierta |

La sustitución de un hilo por una invocación de Lambda no cambia ninguna
de estas firmas.

---

## 7. Lo que falta, dicho claramente

1. **Persistencia en DynamoDB.** Hoy todo es SQLite. Hace falta una
   implementación de la tabla única de arriba. (La capa DynamoDB anterior
   del repo se borró en la poda; es recuperable de git, pero su modelo de
   datos no cubre revisiones ni jobs.)
2. **Almacén de ficheros en S3.** El diccionario se lee hoy de disco
   local (`revisions_db.files_dir`). Es un punto único que cambiar.
3. **Idempotencia.** Si Step Functions reintenta una tarea, hoy se
   persistiría el control dos veces: `_persist_dqc_items` genera ids
   nuevos en cada llamada. Hay que derivar el id del control de
   `(job_id, idx)` antes de desplegar esto. **Es un bug latente también en
   local**, no solo en AWS.
4. **Handlers y despliegue.** `lambda_handler`, la máquina de estados ASL
   y la IaC. No se han escrito: sin cuenta AWS no serían verificables, y
   el acuerdo fue no meter código sin probar en el repo.
5. **Driver de base de datos.** `DatabaseExecutor` está probado contra
   sqlite3 (que es DB-API 2.0, como el driver real). Contra Oracle hará
   falta `oracledb` en la imagen de la Lambda y un ajuste del dialecto en
   el prompt de generación: hoy pide sintaxis SAS/ANSI.

---

## 8. Cuándo NO haría esto

Si el catálogo típico son 10-20 reglas sobre una tabla que cabe en
memoria, esta arquitectura es peor que el contenedor actual: mismo
resultado, más piezas que operar, 25-35 $/mes fijos de red y un
despliegue que ya no se prueba en un portátil. El punto en que empieza a
compensar está en el orden de **50+ reglas por lote, o cualquier volumen
si "sin servidores" es un requisito del cliente**.
