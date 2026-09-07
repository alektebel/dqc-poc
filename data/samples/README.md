# Sample data

Sample inputs for the DQC generator PoC — enough to run the whole flow
(dictionary inspection → generation → cases evaluation) without a real
bank extract.

| File | What it is |
|---|---|
| `dqc_field_dictionary.xlsx` | The bundled **field dictionary** (2 sheets: a "Notas" cover + the dictionary). The DQC generator reads this to know each field's name, type, description, nullability and formula. |
| `diccionario_demo.xlsx` | The demo dictionary used by the scripted demo (`demo/demo_server.py`) and the DQC Studio's `?demo=1` mode. |
| `casos_demo.xlsx` | The demo **extracted-cases** workbook: each row violates exactly one known rule, so a generated check can be scored for precision/recall. |
| `recuperatory_cycles.csv` | A 22k-row synthetic **recuperation-cycles dataset** (`mylib.ciclos_recuperacion`). It is the base table the coherence rules in `training/dq/coherence_rules.py` are verified against (0 violations by construction). |
| `reglas_demo.txt` | The natural-language rule list the demo exercises — one rule per branch of the ReAct pipeline. |
| `irb_schema.sql` | The IRB / IFRS 9 schema the dataset is modelled on (reference only). |

## How the pieces fit

1. **`dqc_field_dictionary.xlsx`** → upload to `/api/dqc/generate` (or the
   Studio's **Generar** screen) as the dictionary.
2. **`reglas_demo.txt`** → paste into the rules textarea (one rule per line).
3. **`casos_demo.xlsx`** → upload as the optional data-cases Excel so each
   generated check reports the example violating rows and its
   precision/recall.

Regenerate the demo Excels at any time with:

```bash
python demo/make_fixtures.py
```
