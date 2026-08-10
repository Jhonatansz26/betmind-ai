# AUDITORÍA COMPLETA — ARQUITECTURA E INTEGRACIÓN END-TO-END

> **Fecha:** 2026-08-10  
> **Alcance:** integración entre `apps/api/`, `packages/ml/`, `apps/web/`, configuración local, jobs y workflow de datos.  
> **Documentos base:** `AUDITORIA_BACKEND.md` y `AUDITORIA_FRONTEND.md`.  
> **Criterio:** se describe el comportamiento del código vigente. Las referencias `archivo:línea` apuntan al estado auditado y pueden cambiar si se edita el código.

## Resumen ejecutivo

### Estado estimado

| Área | Preparación aproximada | Lectura rápida |
|---|---:|---|
| Backend | **65%** | Arquitectura modular, pagos y límites implementados, pero con huecos de enforcement, migraciones manuales, jobs sin scheduler y exposición de datos sensibles en logs. |
| Frontend | **65%** | Build y TypeScript pasan, los flujos principales existen, pero no hay tests, lint ejecutable ni caché compartida; varios gates son solo visuales o locales. |
| Integración end-to-end | **50%** | Los caminos normales funcionan en sandbox/local, pero la operación real de pagos, límites Free, reset de contraseña y despliegue todavía tienen riesgos bloqueantes. |

Estas cifras son una estimación de preparación operativa, no una medición de cobertura de código.

### Riesgos principales

1. **Enforcement PRO incompleto:** un usuario anónimo puede recibir la respuesta completa de predicción, incluido EV y Bet Builder, porque `predictions.py` solo recorta cuando existe `current_user_id`; la UI intenta ocultarlo después en el navegador. Además, el límite de generación Free se salta en respuestas cacheadas.
2. **Límites de tickets inconsistentes:** el backend no limita el guardado anónimo a cinco, `claim` no aplica el límite al reclamar tickets anónimos y el frontend convierte cualquier fallo de persistencia remota en un “guardado” local exitoso.
3. **Datos sensibles en logs:** el fallback de password reset imprime el enlace completo con el JWT de recuperación; el arranque también registra los primeros 80 caracteres de `DATABASE_URL`, que pueden incluir usuario y contraseña según el formato de la URL.
4. **Pagos todavía operativamente incompletos:** la integración está en sandbox, la activación depende de webhook y jobs externos, no hay scheduler en el repositorio y el refund solo marca la solicitud, sin ejecutar el reembolso monetario.
5. **Divergencia de despliegue y esquema:** no existe Dockerfile ni configuración de hosting del API/frontend, el frontend no tiene CI propio y PostgreSQL depende de migraciones SQL manuales mientras el runtime ejecuta `create_all()`.

### Recomendación de prioridad

Primero cerrar seguridad y enforcement: eliminar logs sensibles, recortar datos para anónimos en backend, mover el límite de generación antes del retorno de caché y limitar `claim`/guardado de tickets. Después validar un entorno staging con Wompi sandbox, webhook público, jobs programados y migraciones reproducibles. Solo después conviene priorizar la optimización de caché y re-fetching.

## 1. Flujos críticos

### Convenciones de contrato

- **OK:** el contrato se alinea entre cliente y servidor.
- **Riesgo:** funciona en el camino feliz, pero puede fallar o degradarse silenciosamente.
- **Gap:** existe una diferencia real de comportamiento o enforcement.
- **Seguridad:** la diferencia permite acceder o modificar más de lo que la UI promete.

### 1.1 Registro + trial

1. El usuario completa `/cuenta/registro`. La mayoría de edad se valida solo en estado React; no se envía al API.
2. El frontend llama `POST /api/v1/auth/register` desde `lib/auth.ts` con `{ email, password, full_name? }`.
3. FastAPI valida `email`, exige contraseña de 8 a 128 caracteres, crea `users` con `is_pro=false`, genera un JWT propio y devuelve `201` con `{ access_token, token_type }`.
4. El frontend guarda solo `access_token` en `localStorage['betmind_access_token']`, dispara `betmind:auth-changed` y llama a `claimPendingTickets()` sin esperar su resultado.
5. El frontend redirige a `?redirect=` o `/`.
6. El trial no se inicia dentro de `register`. Si el usuario entra desde `/planes?action=trial`, después de tener sesión el frontend llama `POST /api/v1/subscriptions/trial`.
7. Backend bloquea el usuario, crea o recupera `subscriptions`, asigna `status='trial'`, `plan='mensual'`, una duración de siete días y actualiza `users.is_pro=true` y `pro_expires_at`.
8. El frontend guarda la suscripción, dispara refresco de sesión, vuelve a consultar `/users/me` y redirige a `/`.

**Contratos y riesgos:**

| Punto | Estado | Detalle |
|---|---|---|
| Campos de registro | OK | `full_name` es opcional en ambos lados. |
| Contraseña | OK | El backend es la autoridad y aplica el límite 8-128. |
| Mayoría de edad | Gap | La UI exige confirmarla, pero el backend no recibe ni persiste esa aceptación. |
| Claim de tickets | Riesgo | Se dispara en segundo plano y puede no terminar antes de la navegación; los errores solo van a consola. |
| Trial | OK con matiz | El trial es un segundo paso, no parte de `register`; el frontend lo maneja mediante query string. |
| Trial usado previamente | OK | Backend responde `409`; la UI muestra el mensaje del API. |
| Verificación de email | Pendiente | No existe confirmación de correo; producción debe decidir si es necesaria antes de habilitar pagos. |

### 1.2 Login

1. El usuario envía `/cuenta/login`.
2. Frontend llama `POST /api/v1/auth/login` con `{ email, password }`.
3. Backend busca un usuario activo, ejecuta `verify_password` incluso cuando no existe usuario para reducir diferencias de timing y devuelve el JWT propio.
4. Frontend guarda el token, dispara `betmind:auth-changed`, intenta reclamar tickets anónimos y navega a `redirect` o `/`.
5. Las instancias de `useAuthSession()` llaman `GET /api/v1/users/me`; el backend calcula `is_pro` efectivo según `pro_expires_at`.

**Contratos y riesgos:**

- **OK:** el formato de token coincide: `access_token` y `token_type`.
- **Riesgo:** los fetch de auth no usan el timeout común de `apiFetch`; una API caída puede dejar el formulario esperando más tiempo que el resto de la aplicación.
- **Riesgo:** el cliente inspecciona también claves `sb-*-auth-token`, aunque la autenticación activa usa `betmind_access_token`. Puede existir un Bearer que la UI no reconoce como sesión propia.
- **Riesgo:** `hasSession()` comprueba presencia de la clave, no expiración ni estructura válida. La validación real ocurre después en `/users/me`.
- **Riesgo:** `cachedIsPro` es global al módulo, no tiene TTL ni asociación explícita al usuario; `storeToken()` no lo limpia antes de iniciar una nueva sesión.

### 1.3 Pago real: tokenización → activación → webhook → polling

1. Usuario autenticado entra a `/planes` y el frontend llama `GET /api/v1/subscriptions/me`. Un `404` significa que aún no tiene suscripción.
2. `WompiCardForm` llama directamente a Wompi `GET /merchants/{NEXT_PUBLIC_WOMPI_PUBLIC_KEY}` para obtener los contratos de aceptación.
3. El usuario acepta términos y tratamiento de datos y completa la tarjeta.
4. Frontend pide al backend autenticado `GET /api/v1/subscriptions/wompi-tokenization-key`.
5. Backend consulta Wompi con `WOMPI_PUBLIC_KEY` y devuelve la llave pública de tokenización.
6. Frontend cifra los datos de tarjeta en el navegador usando JWE (`RSA-OAEP-256` + `A256GCM`) y envía el payload directamente a Wompi `POST /tokens/cards` con la llave pública.
7. Wompi devuelve `card_token`. El frontend entrega al componente de planes `{ card_token, acceptance_token, accept_personal_auth }`.
8. Frontend llama `POST /api/v1/subscriptions/activate` con `{ card_token, plan, acceptance_token, accept_personal_auth }`.
9. Backend crea una payment source en Wompi, crea la transacción recurrente con importe en centavos, referencia e `integrity_signature`, guarda la transacción local con estado inicial normalmente `PENDING` y devuelve `202 Accepted`.
10. Backend no activa PRO en este punto. El entitlement se concede solo cuando se procesa `transaction.updated` con firma válida.
11. Wompi llama `POST /api/v1/webhooks/wompi`. Backend valida `WOMPI_EVENTS_SECRET`, checksum del header y checksum del payload, ubica `subscription_transactions` por `wompi_transaction_id` y agenda `process_wompi_event` como background task.
12. `apply_transaction_status()` bloquea transacción, suscripción y usuario; ante `APPROVED` marca suscripción `active`, calcula el periodo y activa PRO. Ante `DECLINED`, `ERROR` o `VOIDED` cancela o mantiene trial según el estado.
13. Mientras tanto, frontend consulta `GET /api/v1/subscriptions/me` cada 2,5 segundos durante hasta 30 segundos.
14. Si ve `active`, actualiza `/users/me`, muestra éxito y vuelve a `/`. Si ve rechazo o un estado distinto de `pending_payment`, muestra error. Si se agota el tiempo, informa que el estado se actualizará más tarde.
15. Si se pierde el webhook, `reconcile_pending_subscriptions.py` debe consultar Wompi después de diez minutos. Si llega el fin de periodo, `renew_subscriptions.py` debe crear la transacción recurrente y aplicar gracia ante fallo.

**Contratos y riesgos:**

| Punto | Estado | Detalle |
|---|---|---|
| Campos de activación | OK | Los nombres y valores del frontend coinciden con `SubscriptionActivateRequest`. |
| Llaves Wompi | Riesgo | Hay una llave pública en backend y otra `NEXT_PUBLIC_*` en frontend; deben pertenecer al mismo ambiente y merchant. |
| Sandbox/producción | Gap operativo | El entorno local auditado usa sandbox. Cambiar solo la URL o solo una llave puede producir errores de merchant/tokenización. |
| Confirmación | OK con dependencia | El backend no activa por respuesta síncrona, correctamente depende del webhook; el polling solo observa. |
| Polling | Riesgo | 30 segundos puede ser menor que la confirmación bancaria; el UX lo reconoce, pero no hay botón de reintento dedicado. |
| Timeout Wompi frontend | Riesgo | Los fetch directos de aceptación y tokenización no tienen `AbortController` ni timeout. |
| Refund | Gap | Backend tiene `/refund`, pero solo marca `refund_requested`; no llama un endpoint monetario de Wompi y no existe operación frontend. |
| Jobs | Gap bloqueante | No hay scheduler en el repositorio. Sin cron externo se pierden reconciliaciones y renovaciones. |
| Reintentos webhook | Riesgo | El procesamiento se agenda como `BackgroundTasks`; la respuesta `accepted` puede devolverse antes de que la persistencia termine. Se necesita probar reintentos y observabilidad en staging. |

### 1.4 Generación y guardado de ticket, incluyendo gate Free

#### Generación

1. `/generador` carga `GET /api/v1/matches/?date_filter=today` y `GET /api/v1/leagues/` para construir la interfaz.
2. El frontend calcula `isPro` desde `/users/me` o desde el flag local de desarrollo.
3. La UI permite configurar perfil, número de selecciones, mercados y ligas. El contador local Free `betmind_daily_generations` impide el tercer intento explícito.
4. `TicketGenerator` llama `POST /api/v1/tickets/generate`. Envía `modes`, `league_keys`, `selection_count` y `markets`; no envía `date_filter`.
5. Backend normaliza filtros, consulta predicciones y cuotas almacenadas, calcula una clave Redis y primero intenta devolver una respuesta cacheada.
6. En cache miss, backend cuenta generaciones Free por `user_id` o por IP de cliente en COT. Si el contador supera dos, responde `403`.
7. Backend construye los tickets con `ticket_builder`, guarda la respuesta en Redis por 30 minutos y devuelve tickets, EV total, partidos analizados y timestamp.
8. Frontend mapea la respuesta, selecciona el ticket del modo activo y muestra sus patas.

#### Guardado

1. Usuario pulsa guardar. Frontend aplica un límite local de cinco entradas para usuarios no PRO.
2. `POST /api/v1/tickets/save` recibe `ticket_data`, `total_odds`, `total_ev` y opcionalmente `stake_amount`.
3. Si hay usuario autenticado Free, backend cuenta tickets asociados y rechaza desde el sexto.
4. Si hay sesión PRO o desarrollo autorizado, guarda sin ese límite.
5. Si no hay token, backend crea el ticket con `user_id=NULL`; el frontend conserva un resumen local y después intenta reclamarlo al iniciar sesión.
6. Si el request remoto falla por cualquier motivo, `addToTracking()` crea una entrada local `remote=false` y devuelve `saved=true` a la UI.

**Contratos y riesgos:**

| Punto | Estado | Detalle |
|---|---|---|
| Respuesta de generación | OK | Los campos usados por el mapper coinciden con `TicketGenerateResponse` y `GeneratedTicket`. |
| Fecha | Gap | El generador carga “today” para la UI, pero la generación omite `date_filter` y backend usa la ventana rolling por defecto. Puede mostrar partidos y generar sobre catálogos distintos. |
| Cuota mínima/máxima | Gap | La UI modifica `oddsMin`/`oddsMax`, pero esos valores no se envían al backend ni filtran la generación. |
| Mercados desactivados | Riesgo | Si no queda ningún mercado seleccionado, el cliente omite `markets`; backend interpreta ausencia como todos los mercados. |
| Límite diario | Seguridad | El retorno de Redis ocurre antes del contador diario. Un Free puede repetir una petición que tenga la misma clave cacheada sin consumir el límite backend. El contador local no es una barrera de seguridad. |
| Límite de guardado anónimo | Gap | El límite backend de cinco solo se evalúa cuando hay `current_user_id`; el guardado anónimo es ilimitado por API. |
| Claim | Seguridad | `POST /tickets/claim` no vuelve a aplicar el límite Free. Un usuario puede crear o reunir múltiples tickets anónimos y reclamarlos. |
| Fallo remoto | Riesgo de UX/datos | La UI dice “guardado” aunque solo exista una copia local. El ticket puede no estar en historial remoto ni tener ID reclamable. |
| Historial/deletion | Gap funcional | El botón de eliminar solo modifica `localStorage`; no existe endpoint de borrado remoto. El ticket puede reaparecer al recargar. |

### 1.5 Configuración y uso de Bankroll

1. `/bankroll` monta el paywall si `useProStatus()` indica que el usuario no es PRO.
2. Para PRO, `useBankroll(true)` llama `GET /api/v1/bankroll`.
3. Si responde `404`, la UI muestra setup y envía `POST /api/v1/bankroll` con `initial_capital` y `risk_profile`. El backend exige capital mayor que cero, crea el bankroll y registra un movimiento inicial.
4. Para cambiar riesgo, frontend envía `PATCH /api/v1/bankroll` con `{ risk_profile }`.
5. Para depósito/retiro, frontend envía `POST /api/v1/bankroll/adjust` con `{ amount, reason }`. Backend usa lock, impide capital negativo y registra `manual_adjustment`.
6. Todos los endpoints de bankroll dependen de `require_pro_user`, que valida JWT, usuario activo y `effective_pro(user)` incluyendo expiración.
7. La respuesta incluye capital actual y lista completa de movimientos. El cliente convierte IDs numéricos a strings para sus tipos internos.

**Contratos y riesgos:**

- **OK:** nombres de campos, perfiles de riesgo, tipos de movimiento y respuestas coinciden.
- **OK:** los cuatro endpoints tienen enforcement PRO real en backend.
- **Riesgo de rendimiento:** la página, el generador y cada `TicketCard` pueden montar su propio `useBankroll`, provocando GET repetidos.
- **Gap de enforcement relacionado:** `stake_amount` se acepta al guardar un ticket Free y `PATCH /tickets/{id}/status` no exige PRO. Si el usuario conserva un bankroll creado durante PRO, una cuenta ya degradada puede modificar estados y generar movimientos aunque no pueda leer o ajustar el bankroll por sus endpoints directos.
- **Riesgo de consistencia:** guardar un ticket no debita el stake inicial; la liquidación solo aplica `-stake` al perder o `stake * (odds - 1)` al ganar. Esto es coherente con un modelo de capital que solo registra resultado neto, pero debe documentarse para no interpretarlo como saldo apostado reservado.

### 1.6 Estado de ticket WON/LOST/VOID y efecto en bankroll

1. Historial remoto carga `GET /api/v1/tickets/history` para el usuario autenticado.
2. El usuario cambia el select de estado. Frontend actualiza la fila de forma optimista.
3. Para tickets remotos autenticados, llama `PATCH /api/v1/tickets/{id}/status` con `{ status: 'PENDING'|'WON'|'LOST'|'VOID' }`.
4. Backend bloquea el ticket por usuario y busca un movimiento existente asociado.
5. Si ya existe movimiento y el mismo estado es enviado otra vez, devuelve el movimiento existente sin duplicarlo.
6. Si ya existe movimiento y se intenta cambiar el estado, responde `409` y frontend revierte el cambio optimista.
7. Si el estado es final, el ticket tiene `stake_amount` y existe bankroll, backend bloquea bankroll y aplica:
   - `WON`: `stake_amount * (total_odds - 1)` y tipo `ticket_won`.
   - `LOST`: `-stake_amount` y tipo `ticket_lost`.
   - `VOID`: `0` y tipo `ticket_void`.
8. La transacción de ticket y movimiento se confirma al finalizar la dependencia de sesión DB.
9. Frontend muestra el movimiento recibido; si no existe bankroll, solo cambia el estado.

**Contratos y riesgos:**

- **OK:** el enum y la respuesta con `bankroll_movement` coinciden.
- **OK:** hay lock e idempotencia para evitar doble movimiento.
- **Riesgo:** el endpoint de estado no está protegido por PRO, aunque el frontend solo ofrece stake/bankroll a PRO.
- **Riesgo:** para tickets locales o no remotos el cambio solo se persiste en `localStorage`; no existe efecto backend ni bankroll.
- **Riesgo:** el botón de eliminar no elimina el registro remoto, por lo que el estado local no es fuente de verdad después de una recarga.

### 1.7 Reset de contraseña

1. Usuario entra a `/cuenta/olvide-password` y frontend llama `POST /api/v1/auth/forgot-password` con `{ email }`.
2. Backend siempre devuelve `200` con mensaje neutral, evitando enumeración de usuarios.
3. Si el correo existe, backend crea JWT de propósito `password_reset`, con expiración de 30 minutos, y construye `FRONTEND_URL/cuenta/resetear?token=...`.
4. Envío intenta SMTP, después Resend y finalmente `_log_stub()` si no hay proveedor configurado.
5. Usuario abre el link y `/cuenta/resetear` extrae `token` de query string.
6. Frontend valida longitud de contraseña, confirmación y llama `POST /api/v1/auth/reset-password` con `{ token, new_password }`.
7. Backend valida firma, expiración y `purpose`, busca usuario activo, hashea la nueva contraseña y devuelve `200`.

**Contratos y riesgos:**

- **OK:** nombres `token` y `new_password`, respuesta neutral y TTL coinciden.
- **Seguridad:** `_log_stub()` imprime el enlace completo con el token. Si SMTP y Resend fallan, el JWT queda en logs.
- **Seguridad:** el token JWT no se invalida después de usarlo; puede reutilizarse hasta su expiración. El propio código documenta que no existe tabla de tokens usados.
- **Riesgo operativo:** `FRONTEND_URL` no está configurada en el `.env` local; usa default `http://localhost:3000`. En producción el link de recuperación apuntaría al host equivocado si no se define.
- **Riesgo:** los fetch directos de auth no tienen timeout común.
- **Pendiente de producto:** resetear la contraseña no revoca JWT de sesiones existentes; hay que decidir si se requiere invalidación global.

## 2. Inventario cruzado de variables de entorno

### Criterio de presencia

“Presente” significa que el nombre existe en el archivo local auditado, sin exponer el valor. El `.env` raíz y `apps/web/.env.local` están ignorados por Git y no aparecen como archivos trackeados. Algunos nombres no presentes usan defaults de `config.py` o del código frontend.

### Backend

| Variable | Uso | Obligatoria para | Presente local | Sensibilidad |
|---|---|---|---|---|
| `APP_NAME` | `apps/api/config.py`, metadata FastAPI | No | No, default | Pública |
| `APP_VERSION` | `apps/api/config.py`, health | No | No, default | Pública |
| `DEBUG` | `config.py`, SQL echo y bypass dev | **Sí: debe ser `false` en prod** | Sí | Configuración no secreta, peligrosa si queda activa |
| `ALLOWED_ORIGINS` | `main.py`, CORS | **Sí para producción** | No, default local | Pública |
| `DATABASE_URL` | `db/database.py`, jobs y scripts | **Sí** | Sí | **Sensible**, contiene credenciales |
| `REDIS_URL` | `cache_service.py`, slowapi, rate limit | **Sí recomendado en prod** | Sí | **Sensible** si contiene contraseña |
| `DB_POOL_SIZE` | `db/database.py` | No | No, default | No sensible |
| `DB_MAX_OVERFLOW` | `db/database.py` | No | No, default | No sensible |
| `DB_POOL_TIMEOUT` | `db/database.py` | No | No, default | No sensible |
| `API_FOOTBALL_KEY` | `api_football.py`, sync | Sí para datos API-Football | Sí | **Sensible** |
| `FOOTBALL_DATA_KEY` | proveedor alternativo | No, pero necesaria para fallback | Sí | **Sensible** |
| `GROQ_API_KEY` | `config.py`, fallback de LLM | No si existe `GROQ_API_KEYS` | No | **Sensible** |
| `GROQ_API_KEYS` | `llm_cascade.py`, rotación de keys | No si existe key simple | Sí | **Sensible** |
| `GEMINI_API_KEY` | fallback LLM | No | Sí | **Sensible** |
| `ANTHROPIC_API_KEY` | AI Search Agent | No, solo fallback BetPlay | No | **Sensible** |
| `SECRET_KEY` | JWT propio y fallback de firma | **Sí y debe ser fuerte** | Sí | **Secreta crítica** |
| `SUPABASE_JWT_SECRET` | validación de JWT Supabase/propio | No si se usa solo JWT propio | Sí | **Secreta crítica** |
| `SUPABASE_JWT_AUDIENCE` | declarada en `config.py` | No | No, default | No sensible, actualmente no usada |
| `ALGORITHM` | firma JWT | No, default `HS256` | No, default | Configuración |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | TTL de sesión | No, default 10080 | No, default | Configuración |
| `ADMIN_API_KEY` | `X-Admin-Key` de backtesting | Sí si se habilita backtesting admin | No | **Sensible** |
| `FRONTEND_URL` | links de password reset | **Sí en producción** | No, default localhost | Pública |
| `RESEND_API_KEY` | email de reset, fallback 2 | Sí si no se usa SMTP | Sí | **Sensible** |
| `EMAIL_FROM_ADDRESS` | remitente SMTP/Resend | Sí junto con proveedor de email | Sí, repetida en `.env`; prevalece la última definición | Configuración pública |
| `SMTP_SERVER` | proveedor SMTP | No si se usa Resend | Sí | No sensible |
| `SMTP_PORT` | proveedor SMTP | No si se usa Resend | Sí | No sensible |
| `SMTP_USERNAME` | autenticación SMTP | Sí si se usa SMTP | Sí | Sensible operacional |
| `SMTP_PASSWORD` | autenticación SMTP | Sí si se usa SMTP | Sí | **Sensible** |
| `WOMPI_BASE_URL` | API Wompi sandbox/prod | **Sí para pagos** | Sí, sandbox | Pública/configuración |
| `WOMPI_PUBLIC_KEY` | merchant lookup y tokenización | **Sí para pagos** | Sí, sandbox | Pública |
| `WOMPI_PRIVATE_KEY` | payment sources y transacciones | **Sí para pagos** | Sí, sandbox | **Secreta crítica** |
| `WOMPI_INTEGRITY_SECRET` | firma de transacción | **Sí para pagos** | Sí, sandbox | **Secreta crítica** |
| `WOMPI_EVENTS_SECRET` | validar webhooks | **Sí para pagos** | Sí, sandbox | **Secreta crítica** |
| `WOMPI_MONTHLY_AMOUNT_CENTS` | importe mensual | No, default | No, default | No sensible |
| `WOMPI_ANNUAL_AMOUNT_CENTS` | importe anual | No, default | No, default | No sensible |
| `SUBSCRIPTION_GRACE_DAYS` | gracia de renovación | No, default 3 | No, default | No sensible |
| `PENDING_PAYMENT_RECONCILE_DELAY_MINUTES` | delay del job de reconciliación | No, default 10 | No, default | No sensible |
| `GROQ_TIMEOUT_SECONDS` | timeout del orquestador | No, default 90 | No, default | No sensible |
| `GROQ_SINGLE_CALL_TIMEOUT` | timeout de una llamada Groq | No, default 25 | No, default | No sensible |
| `GROQ_NARRATIVE_TIMEOUT` | timeout narrativo | No, default 80 | No, default | No sensible |

### Frontend

| Variable | Uso | Obligatoria para | Presente local | Sensibilidad |
|---|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | `apps/web/lib/api.ts`, `lib/auth.ts` | No en local; **sí para producción** | Sí | Pública |
| `NEXT_PUBLIC_WOMPI_BASE_URL` | `apps/web/lib/wompi.ts` | No por default; **sí para cambiar a prod** | Sí, sandbox | Pública |
| `NEXT_PUBLIC_WOMPI_PUBLIC_KEY` | merchant lookup y tokenización desde navegador | Sí para pagar desde frontend | Sí, sandbox | Pública |

### Observaciones de configuración

- El `.env.example` raíz no documenta todas las variables reales de `config.py`: faltan, entre otras, `FRONTEND_URL`, `SUPABASE_JWT_SECRET`, las variables Wompi, los importes y los timeouts.
- El `.env.example` declara `ACCESS_TOKEN_EXPIRE_MINUTES=30`, pero el default vigente en `config.py` es 10080 minutos, siete días.
- El `.env` local tiene `DEBUG` definido dos veces. También define `EMAIL_FROM_ADDRESS` dos veces; debe quedar una sola definición explícita.
- El entorno local contiene credenciales reales de proveedores sandbox y servicios externos. Aunque el archivo esté ignorado por Git, deben rotarse si fueron compartidas, copiadas a logs o expuestas fuera del equipo.
- `WOMPI_PUBLIC_KEY` es segura para cliente; `WOMPI_PRIVATE_KEY`, secretos de integridad/eventos y cualquier URL con credenciales nunca deben llegar al bundle Next.

## 3. Deploy: qué falta para producción

### Bloqueantes técnicos

- [ ] Configurar un `DATABASE_URL` PostgreSQL de producción con TLS, pool adecuado y credenciales gestionadas por el proveedor.
- [ ] Aplicar y verificar las migraciones 004-017 en staging y producción; documentar el baseline de las tablas 001-003 que no tienen archivos SQL.
- [ ] Resolver la doble fuente de esquema: `Base.metadata.create_all()` en el startup local/API frente a migraciones SQL manuales para PostgreSQL. Idealmente usar un único migrador reproducible y evitar cambios silenciosos de schema al arrancar.
- [ ] Definir el runtime del backend. No hay `Dockerfile`, manifiesto de hosting ni comando de producción versionado para la API.
- [ ] Definir el hosting del frontend Next y proveer `NEXT_PUBLIC_API_URL` de producción; no existe configuración de despliegue ni workflow web en el repositorio.
- [ ] Crear TLS, dominio, health checks de readiness para DB/Redis y política de reinicio del API.
- [ ] Configurar `ALLOWED_ORIGINS` únicamente con dominios de producción y revisar que `allow_credentials=True` sea necesario para el modelo de auth actual.
- [ ] Establecer `DEBUG=false` y reemplazar `SECRET_KEY` por un secreto fuerte gestionado fuera del repositorio.

### Pagos y suscripciones

- [ ] Cambiar juntas `WOMPI_BASE_URL`, `WOMPI_PUBLIC_KEY`, `WOMPI_PRIVATE_KEY`, `WOMPI_INTEGRITY_SECRET`, `WOMPI_EVENTS_SECRET` y las dos variables públicas frontend a producción.
- [ ] Verificar que ambas llaves públicas correspondan al mismo merchant y ambiente.
- [ ] Registrar en Wompi una URL HTTPS pública para `/api/v1/webhooks/wompi` y validar eventos reales de aprobación, rechazo, duplicado y reintento.
- [ ] Desplegar `reconcile_pending_subscriptions.py` con frecuencia inferior al SLA esperado y `renew_subscriptions.py` al menos diariamente; usar un scheduler externo con logs y alertas.
- [ ] Definir una estrategia de idempotencia y retry observable para el webhook; comprobar que un proceso terminado antes de `BackgroundTasks` no deje transacciones sin aplicar.
- [ ] Implementar o documentar formalmente el proceso de refund monetario. Hoy `/refund` solo revoca PRO y marca `refund_requested`.
- [ ] Probar activación desde trial, pago aprobado, pago pendiente, pago rechazado, renovación aprobada, renovación fallida y fin de gracia.
- [ ] Añadir timeouts/reintentos controlados a los fetch directos del frontend hacia Wompi.

### Seguridad y cumplimiento

- [ ] Eliminar `_log_stub()` o reemplazarlo por un mecanismo seguro que nunca escriba el token de reset. No usar el log como canal de entrega en producción.
- [ ] Eliminar el log parcial de `DATABASE_URL` y revisar handlers de excepciones para que nunca serialicen credenciales, payloads de pago o headers.
- [ ] Rotar las credenciales actualmente presentes en el `.env` local si han salido del entorno de confianza.
- [ ] Corregir el recorte de predicciones para usuarios anónimos en backend; no confiar en blur, `slice()` ni gates del cliente.
- [ ] Mover el enforcement del contador de generación antes del retorno de caché y hacer que la clave/cuenta esté alineada con la política de abuso.
- [ ] Aplicar límite Free en guardado anónimo y en `claim`, y decidir si `PATCH /tickets/{id}/status` debe requerir PRO cuando existe stake/bankroll.
- [ ] Proteger o retirar `POST /matches/sync/{league_id}` y `POST /matches/sync-all`: actualmente son públicos y pueden consumir cuotas o recursos de ingesta.
- [ ] Decidir si se requiere verificación de email, revocación de sesiones después de reset y persistencia de aceptación de mayoría de edad.
- [ ] Configurar proveedor de email con dominio verificado, SPF/DKIM/DMARC, `FRONTEND_URL` correcto y monitorización de entregabilidad.

### Calidad y operación

- [ ] Añadir tests de integración HTTP para auth, trial, pagos, webhook, tickets, claim, bankroll y estados.
- [ ] Añadir tests frontend o E2E para registro/login, gates Free/PRO, guardado remoto/local, polling Wompi y cambio de estado.
- [ ] Añadir ESLint al frontend y un script `test`; hoy `npm run lint` falla porque `eslint` no está instalado y `npm test` no existe.
- [ ] Crear CI que ejecute backend tests, TypeScript, lint y build de Next. El workflow actual solo ejecuta ingesta y predicciones Python.
- [ ] Elegir un único gestor de paquetes frontend o hacer que ambos lockfiles se mantengan deliberadamente sincronizados.
- [ ] Preparar backups/restores de PostgreSQL y alertas para errores de DB, Redis, Wompi, jobs y proveedor de datos.
- [ ] Definir límites y presupuesto para API-Football, Football Data, Groq, Gemini, Anthropic y scrapers; verificar que Playwright/crawl4ai estén disponibles en el runtime que se elija.

## 4. Rendimiento: diagnóstico conjunto

### Causa raíz más probable

El síntoma de queries repetidas tiene una causa primaria en frontend y una causa amplificadora en backend:

1. El frontend no tiene React Query, SWR, cache HTTP ni provider global. `HomePage`, `MatchesPage` y `GeneratorPage` solicitan `/matches/` de forma independiente; `MatchesPage` y `GeneratorPage` también solicitan `/leagues/` por separado.
2. Cada instancia de `useAuthSession`, `useBankroll` o `useTicketHistory` ejecuta su propio ciclo. Una pantalla con varias `TicketCard` puede repetir `/users/me` y `/bankroll`.
3. El backend no cachea endpoints de matches. Cada request repetido vuelve a ejecutar aproximadamente seis queries en la lista, nueve en detalle y unas once en H2H.
4. La lista de matches hace dos round-trips separados para `home_team` y `away_team`, y existe riesgo de double-loading de relaciones declaradas `selectin` pero cargadas también manualmente.

Por tanto, no parece un N+1 clásico. El patrón más probable es **duplicación de requests HTTP desde componentes independientes**, multiplicada por **ausencia de caché de lectura en backend**. Si tres consumidores piden la misma lista en una ventana corta, el backend puede ejecutar unas 18 queries SQL aunque cada request individual use `selectinload` correctamente.

### Esbozo de solución futura, sin implementación en esta auditoría

| Capa | Medida posible | Prioridad |
|---|---|---:|
| Frontend | Añadir React Query o SWR con keys estables, `staleTime`/`dedupingInterval`, invalidación después de login, trial, guardado y cambio de estado | Alta |
| Frontend | Centralizar sesión, PRO y bankroll en providers/hooks compartidos | Alta |
| Frontend | Cancelar requests obsoletos cuando cambia fecha, filtros o partido | Media |
| Backend | Cachear lista, detalle y H2H en Redis con TTL corto, por ejemplo 30-60 segundos para cartelera | Alta |
| Backend | Mantener caché de predicciones/táctica con invalidación al sincronizar datos | Media |
| Backend | Revisar joins/eager loading de equipos y ligas para reducir round-trips sin volver a un N+1 | Media |
| Backend | Separar respuesta de cartelera de respuesta de detalle y devolver solo los campos necesarios | Media |
| Datos | Medir p50/p95, hits de caché, queries por endpoint y ratio de respuestas duplicadas antes/después | Alta |

La solución más rentable probablemente sea **caché/deduplicación en frontend primero**, porque elimina requests duplicados entre componentes, seguida de **Redis para lecturas de matches** para absorber recargas, pestañas y múltiples usuarios. Optimizar joins sin corregir la duplicación HTTP aliviaría cada request, pero no la causa principal.

## 5. Riesgos de seguridad cruzados

### 5.1 Datos sensibles en logs

| Dato | Resultado de la revisión | Evidencia |
|---|---|---|
| Contraseñas en texto claro | No se encontraron logs directos de contraseñas. Se hashean con bcrypt antes de persistir. | `auth.py`, `auth_service.py` |
| Hashes de contraseña | No se registran explícitamente. | `auth.py:58-70` |
| JWT de sesión | No se registra explícitamente en API ni frontend. Se guarda en `localStorage`, que es una superficie de riesgo XSS pero no un log. | `auth.ts`, `api.ts` |
| Token de reset | **Expuesto en fallback de logs.** `_log_stub()` escribe el `reset_link` completo, incluyendo JWT válido por 30 minutos. | `auth_service.py:110-117` |
| URL de base de datos | **Riesgo de exposición.** El constructor registra `DATABASE_URL[:80]`; con el formato actual puede incluir credenciales antes del `@`. | `config.py:162` |
| Llave privada Wompi | No se vio logging directo de `WOMPI_PRIVATE_KEY`; `httpx`/`httpcore` se bajan a WARNING. | `wompi_service.py:12-15,94-105` |
| Tokens de tarjeta/CVC | No se encontraron `console.log` de los campos de tarjeta ni logging backend de payload de tarjeta. | `wompi.ts`, `wompi-card-form.tsx` |
| API keys de proveedores | API-Football se envía en header y las URLs logueadas no incluyen ese header. Wompi usa llave pública en URL, que no es secreta. | `api_football.py`, `wompi_service.py` |
| Payloads de errores externos | No se observó log directo de `WompiAPIError.payload`; aun así, los handlers genéricos deben revisarse para no imprimir excepciones de proveedores sin sanitizar. | `main.py`, `subscriptions.py` |

La respuesta a “¿está limpio el logging?” es **no**. El ajuste de `httpx/httpcore` evitó una familia de fugas de credenciales de transporte, pero no cubrió el token de reset ni la URL de DB.

### 5.2 Enforcement PRO frente a lo que asume el frontend

| Feature | Suposición visible en frontend | Enforcement backend | Evaluación |
|---|---|---|---|
| Bankroll GET/setup/patch/adjust | Solo PRO puede usarlo | `require_pro_user` en los cuatro endpoints | **Correcto** |
| Bet Builder | Free ve blur/CTA y PRO ve datos | Backend vacía `bet_builder` solo si hay usuario autenticado Free | **Hueco anónimo:** anónimo recibe datos completos |
| EV/mercados de predicción | Free ve una parte | Backend recorta a 10 solo con `current_user_id` | **Hueco anónimo:** recorte client-side no protege payload |
| Generación diaria | Free 2 por día; PRO ilimitado | Backend cuenta por usuario/IP en Redis | **Hueco por cache:** hit retorna antes de contar |
| Tickets guardados | Free 5, PRO ilimitado | Cuenta solo usuario autenticado; anónimo sin límite | **Desalineado** |
| Claim de tickets | Tras login se reclaman tickets locales | Reclama IDs anónimos sin contar límite Free | **Desalineado y abusables** |
| Stake/bankroll en ticket | UI solo abre stake para PRO con bankroll | Save acepta stake Free; status no exige PRO | **Hueco de autorización contextual** |
| Flag de desarrollo PRO | Solo visible fuera de producción | Backend lo acepta solo si `DEBUG=true` | **Correcto si `DEBUG=false`; verificar configuración** |
| Suscripción/trial | Operaciones disponibles a usuario logueado | Endpoints requieren JWT | **Correcto** |

El frontend no debe considerarse una barrera de seguridad. La protección real debe ocurrir antes de serializar la respuesta en FastAPI y dentro de cada mutación.

### 5.3 Otras superficies cruzadas

- El token propio se guarda en `localStorage`, por lo que un XSS permitiría robar sesión. No hay cookies HttpOnly porque el diseño actual es bearer token desde cliente.
- CORS permite credenciales, todos los métodos y todos los headers; el conjunto de orígenes sí está restringido por configuración, pero el default local no sirve para producción.
- Los endpoints de sincronización de partidos son públicos y pueden producir abuso de cuota o carga externa.
- RLS existe en Supabase, pero la API conecta directamente con la base de datos y sus permisos efectivos deben verificarse con el rol de conexión de producción. No asumir que RLS compensa una autorización ausente en la API.
- El reset de contraseña no invalida tokens existentes ni tokens de reset ya usados.

## 6. Resumen de contratos y desalineaciones

| Área | Backend entrega | Frontend espera/hace | Resultado |
|---|---|---|---|
| Auth | JWT propio con `access_token`, `token_type` | Guarda y envía Bearer | Alineado |
| Trial | Suscripción `trial`, PRO por 7 días | Refresca `/users/me` y redirige | Alineado |
| Pago | `202 pending_payment`, activación solo por webhook | Hace polling de `/subscriptions/me` | Alineado, dependiente de jobs/webhook |
| Predicción | Respuesta completa para anónimo por condición actual | Oculta parte en cliente | **Fuga de datos** |
| Generación | `date_filter` opcional; default rolling | Carga “today” pero no envía fecha | **Desalineado** |
| Filtros de cuota | No existen en request | UI permite `oddsMin`/`oddsMax` | **Solo presentación** |
| Mercados vacíos | Ausencia interpreta todos | UI puede representar ninguno | **Desalineado** |
| Guardado Free | Límite autenticado de cinco | Límite local de cinco | **No cubre anónimo/claim/fallos remotos** |
| Bankroll | IDs numéricos y respuesta completa | Mapea a strings | Alineado |
| Estados | Enum y movimiento opcional | Actualización optimista y toast | Alineado con riesgo de local-only |
| Refund | Endpoint backend sin cobro monetario | No tiene wrapper ni UI | **Feature incompleta** |
| Password reset | Respuesta neutral y JWT de 30 min | Query string y POST | Alineado, pero logs/reutilización inseguros |

## 7. Checklist de aceptación antes de producción

El sistema no debería considerarse production-ready hasta que, como mínimo:

- [ ] Ningún log contiene reset links, credenciales de DB, tokens, datos de tarjeta o secretos.
- [ ] Una petición anónima a predicciones recibe exactamente el mismo recorte que un Free autenticado.
- [ ] Repetir una generación cacheada no permite superar el límite Free.
- [ ] Guardado anónimo y `claim` respetan la política de cinco tickets o se documenta explícitamente una política distinta.
- [ ] Un usuario degradado no puede usar una mutación de ticket para modificar bankroll fuera de la política PRO.
- [ ] Wompi sandbox se prueba end-to-end con webhook, polling, reconciliación y renovación.
- [ ] Wompi producción usa llaves coherentes, URL HTTPS y secretos gestionados.
- [ ] Password reset funciona con un proveedor real, `FRONTEND_URL` de producción y no deja tokens reutilizables según la política elegida.
- [ ] Las migraciones de PostgreSQL son reproducibles y están verificadas contra los modelos ORM.
- [ ] Jobs de reconciliación y renovación tienen scheduler, alertas y lock/concurrencia verificados.
- [ ] CI ejecuta tests backend, TypeScript, lint y build frontend.
- [ ] Se dispone de backups, restauración probada, observabilidad y límites de proveedores externos.

## Fuentes consultadas

- `AUDITORIA_BACKEND.md`
- `AUDITORIA_FRONTEND.md`
- `apps/api/config.py`
- `apps/api/dependencies.py`
- `apps/api/routes/v1/auth.py`
- `apps/api/routes/v1/tickets.py`
- `apps/api/routes/v1/subscriptions.py`
- `apps/api/routes/v1/bankroll.py`
- `apps/api/routes/v1/predictions.py`
- `apps/api/repositories/ticket_repository.py`
- `apps/api/services/auth_service.py`
- `apps/api/services/subscription_service.py`
- `apps/api/services/wompi_service.py`
- `apps/api/jobs/reconcile_pending_subscriptions.py`
- `apps/api/jobs/renew_subscriptions.py`
- `apps/web/lib/api.ts`
- `apps/web/lib/auth.ts`
- `apps/web/lib/subscriptions.ts`
- `apps/web/lib/bankroll.ts`
- `apps/web/lib/tracking.ts`
- `apps/web/lib/wompi.ts`
- `apps/web/app/planes/page.tsx`
- `apps/web/components/betmind/ticket-generator.tsx`
- `apps/web/components/betmind/tracking-panel.tsx`
- `apps/web/components/betmind/history-page.tsx`
