/* ─────────────────────────────────────────────────────────────────────────
 * RELLENA ESTO. Es el único fichero que hay que tocar para conectar la
 * aplicación a tu API.
 *
 * Mientras BASE_URL esté vacía la app funciona en modo local: tus ficheros
 * se leen y las consultas se ejecutan de verdad en el navegador, pero nadie
 * deriva la SQL desde lenguaje natural (la escribes tú) y nada se guarda
 * fuera de esta pestaña.
 *
 * El contrato completo de las cuatro rutas, con ejemplos de petición y
 * respuesta y el esquema de DynamoDB, está en docs/API_CONTRACT.md.
 * ───────────────────────────────────────────────────────────────────────── */

export const CONFIG = {
  /** URL base de tu API, sin barra final.
   *  Ej: 'https://abc123.execute-api.eu-west-1.amazonaws.com/prod'
   *  Vacío = modo local. */
  BASE_URL: '',

  /** Clave que tu API espera. Se envía en la cabecera indicada abajo.
   *  Deja vacío si tu endpoint no pide clave (p. ej. si va por IAM o Cognito).
   *
   *  AVISO: esto viaja al navegador. No pongas aquí una credencial de AWS ni
   *  nada que dé más permisos que "invocar este endpoint". La clave de
   *  Bedrock vive en tu Lambda, nunca aquí. */
  API_KEY: '',

  /** Cabecera donde va API_KEY. 'x-api-key' es lo que espera API Gateway
   *  con una API key; usa 'Authorization' si tu endpoint valida un bearer. */
  API_KEY_HEADER: 'x-api-key',

  /** Segundos de espera para la llamada al modelo. Derivar una consulta
   *  puede tardar: un timeout corto se traduce en fallos que parecen del
   *  modelo y son del cliente. */
  TIMEOUT_S: 120,
};

/** True cuando hay una API que llamar. */
export function hasApi() {
  return Boolean(CONFIG.BASE_URL);
}
