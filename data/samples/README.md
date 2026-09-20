# Datos de ejemplo

Suficiente para recorrer el flujo entero (revisión → diccionario → reglas →
informe) sin un extracto real de banco.

| Fichero | Qué es |
|---|---|
| `dqc_field_dictionary.xlsx` | Diccionario de campos con 2 hojas (una portada "Notas" + el diccionario). Sirve para comprobar la selección de hoja. |
| `diccionario_demo.xlsx` | Diccionario de una sola hoja, el camino corto. |
| `casos_demo.xlsx` | Tabla de casos: cada fila incumple exactamente una regla conocida, de modo que un control generado puede puntuarse en precisión/recall. |
| `reglas_demo.txt` | Lista de reglas en lenguaje natural — una por rama del pipeline. |

Uso: `diccionario_demo.xlsx` en el paso 2 y `casos_demo.xlsx` como tabla del
paso 1; luego pega las líneas de `reglas_demo.txt` o súbelo entero en el
paso 3.
