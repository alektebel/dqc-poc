# Benchmark DQC — PD/LGD

Estado: **diseño**. Aquí aún no hay código; este documento fija el contrato
antes de escribirlo.

## Qué mide

Dada una base de reporting PD/LGD con errores sembrados, un diccionario de
campos y las directrices EBA/GL/2017/16, ¿qué parte de los errores detecta el
sistema evaluado con los controles que genera, y a qué coste en falsos
positivos?

## Principios (no negociables)

1. **Ground truth ejecutable.** Cada mutación lleva un `oracle_sql` que la
   detecta. La base limpia pasa todos los oráculos; si alguno salta sobre la
   base limpia, el fallo es del benchmark.
2. **Todo error se puede resolver con lo que recibe el sistema.** Un campo con
   un nombre raro es válido solo si el diccionario o el changelog lo explican.
   Si no hay forma de saberlo, el benchmark está midiendo suerte.
3. **Cada fallo se puede atribuir a una causa.** Se evalúan por separado:
   (a) vinculación de campos (*schema linking*), (b) recuperación normativa
   (RAG frente a contexto perfecto) y (c) generación del control.
4. **Los falsos positivos se penalizan.** Un control que salta sobre la base
   limpia cuenta en contra; si no, gana quien lance más controles.
5. **Hay un conjunto reservado (held-out).** Un subconjunto de mutaciones (y
   a ser posible un esquema entero) que no se mira mientras se desarrolla la
   herramienta.
6. **Los datos no se guardan en Excel.** Excel convierte fechas por su
   cuenta, quita ceros a la izquierda y cambia tipos. El diccionario y el
   catálogo de mutaciones pueden ir en Excel; los datos van en SQLite o
   Parquet.

## Estructura prevista

```
benchmark/
  spec/
    diccionario.xlsx        # tablas, campos, tipos, dominios, reglas, ref. normativa (§N)
    changelog.xlsx          # evolución de campos por versión/partición
    mutaciones.xlsx         # catálogo: id, familia, tabla/campo, regla violada, §N, dificultad, split
  generator/
    clean.py                # base limpia coherente por construcción (seed fijo)
    mutate.py               # aplica mutaciones → trap DBs (k filas por mutación) + mixed DB
  oracle/
    oracles.sql             # un oracle_sql por mutación
    selftest.py             # base limpia = 0 disparos; cada trap = su oráculo dispara
  adapters/
    base.py                 # contrato: (diccionario, instrucciones, contexto) → list[SQL]
    ...                     # un adaptador por sistema a comparar
  scoring/
    score.py                # recall por familia / §N / dificultad, FP rate, schema-linking recall
  build/                    # generado (gitignored)
  runs/                     # resultados por sistema y fecha (gitignored)
```

## Contrato con el sistema evaluado

- **Entrada:** `diccionario.xlsx` (sin columnas de ground truth),
  instrucciones en lenguaje natural, y, según la condición, nada / top-k del
  RAG / párrafos exactos.
- **Salida:** lista de controles SQL que devuelven las filas infractoras.
- **Puntuación:** cada SQL se ejecuta sobre la base limpia y sobre cada trap
  DB. Un error cuenta como detectado si el control marca al menos las k filas
  sembradas y no marca nada en la base limpia.

## Familias de mutaciones (borrador)

| Familia | Ejemplo | Referencia normativa |
|---|---|---|
| Rango / dominio | PD fuera de (0,1], LGD < 0 | GL §… |
| Suelos y conservadurismo | PD por debajo del suelo del 0,03 %; LGD downturn < LGD | CRR 160, GL §… |
| Definición de default | días de impago > 90 sin marca de default | CRR 178 |
| Coherencia entre tablas | EAD en la tabla de Basilea ≠ EAD en la tabla de PD | — |
| Temporal / particiones | mismo contrato con segmento distinto entre fechas de referencia sin evento | GL §… |
| Evolución de esquema | campo renombrado o recodificado en v2, con la partición antigua aún con el dominio viejo | changelog |
| Interdependencias | margen de cautela total ≠ A+B+C; LGD in-default < ELBE | GL §43–44, §… |

Las referencias `§…` se rellenan contra el JSON de párrafos, nunca de memoria.

## Decisiones abiertas

1. Qué PDF(s) forman el corpus: solo EBA/GL/2017/16, o también CRR arts.
   178–181, los RTS de downturn y la guía de la definición de default.
2. Qué sistemas se van a comparar y cómo se invocan (endpoint HTTP, CLI,
   prompt fijo).
3. Tamaño: número de tablas, campos, filas y particiones.
4. Quién escribe y valida las mutaciones difíciles. Si las diseña uno de los
   modelos que se comparan, el benchmark lleva sus sesgos.
