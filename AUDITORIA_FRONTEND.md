# AUDITORÍA COMPLETA - FRONTEND BetMind AI

> **Fecha:** 2026-08-09  
> **Alcance:** `apps/web/`  
> **Criterio:** inventario factual del código vigente, con referencias de archivo y línea. No se aplicaron cambios de código de aplicación.  
> **Verificación ejecutada:** `npx.cmd tsc --noEmit --incremental false`, `npm.cmd run build`, `npm.cmd run lint`, `npm.cmd test` y un chequeo adicional con `noUnusedLocals/noUnusedParameters`.

---

## 1. Arquitectura general

### Stack

| Capa | Tecnología | Versión declarada | Evidencia / notas |
|---|---|---:|---|
| Framework | Next.js App Router | `16.2.6` | `apps/web/package.json:18`; las rutas se definen bajo `app/`. |
| UI | React + React DOM | `^19` | `apps/web/package.json:19-20`. El build identifica React `19.2.4` desde los lockfiles. |
| Lenguaje | TypeScript | `5.7.3` | `apps/web/package.json:33`; `strict: true`, `noEmit: true`, resolución `bundler`: `apps/web/tsconfig.json:8-19`. |
| CSS | Tailwind CSS 4 + PostCSS | `^4.3.3`, `^8.5` | `apps/web/package.json:27-32`; tokens y utilities en `apps/web/app/globals.css:1-55,144-335`. |
| Primitivas UI | `@base-ui/react` + configuración shadcn | `^1.5.0`, shadcn `^4.8.0` | `apps/web/components.json:1-20`; Button, Dialog, Card y otros en `components/ui/`. |
| Variantes/clases | `class-variance-authority`, `clsx`, `tailwind-merge` | declaradas | `apps/web/package.json:12-14,23`. `cn()` vive en `apps/web/lib/utils.ts`. |
| Iconos | `lucide-react` | `^1.16.0` | Importado por las rutas y componentes de producto. |
| Notificaciones | `sonner` | `^2.0.7` | Toaster global en `apps/web/app/layout.tsx:3,74-75`; wrapper en `components/ui/sonner.tsx`. |
| Criptografía cliente | `jose` | `^6.2.8` | Se usa exclusivamente para el JWE de Wompi: `apps/web/lib/wompi.ts:3,81-86`. |
| Motion | `framer-motion` | `^12.43.0` | Está en `package.json:15`, pero no hay imports en `apps/web`. Las animaciones activas son CSS. |
| Gráficos | SVG, CSS y Canvas propios | sin SDK | `poisson-mini-chart.tsx`, `bankroll-page.tsx`, radar del detalle y `lib/ticket-export.ts`. No hay Recharts, Chart.js, D3 ni Visx. |
| Fuentes | `next/font/google` | integrado en Next | Inter, Playfair Display e IBM Plex Mono: `apps/web/app/layout.tsx:2,19-33`. |
| Estado externo | Ninguno | - | No hay Redux, Zustand, Jotai, React Query ni SWR en `package.json`. El estado vive en hooks y componentes React locales. |

### Estructura de carpetas

```text
apps/web/
├── app/                         # App Router: layouts, páginas y CSS global
│   ├── page.tsx                 # Inicio
│   ├── senales/                 # Señales +EV
│   ├── generador/               # Generador de boletos
│   ├── partidos/                # Cartelera y detalle dinámico
│   ├── historial/               # Historial de boletos
│   ├── bankroll/                # Bankroll PRO
│   ├── planes/                  # Suscripciones y Wompi
│   └── cuenta/                  # Login, registro y recuperación
├── components/
│   ├── betmind/                 # Componentes de producto y hooks de feature
│   └── ui/                      # Primitivas Base UI/shadcn adaptadas
├── lib/
│   ├── hooks/                   # use-auth-session.ts
│   ├── api.ts                   # Cliente HTTP, contratos y mapeadores
│   ├── auth.ts                  # JWT propio y /users/me
│   ├── subscription.ts          # Estado PRO y flag de desarrollo
│   ├── subscriptions.ts         # Operaciones de suscripción
│   ├── bankroll.ts              # Cliente y tipos de bankroll
│   ├── betmind.ts               # Tipos, Poisson y cálculo frontend de EV
│   ├── tracking.ts              # Persistencia local y claim de tickets
│   ├── wompi.ts                 # Aceptaciones, JWE y tokenización
│   ├── theme.ts                 # Tema local/cookie
│   └── formatters*.ts           # Fechas, COP, cuotas, EV y mercados
├── public/                      # Iconos y assets estáticos
├── next.config.mjs              # Configuración de imágenes remotas
├── components.json              # Configuración shadcn
└── package.json                 # Scripts y dependencias
```

La configuración de shadcn declara el alias de hooks como `@/hooks` (`apps/web/components.json:13-19`), pero el único hook de `lib/hooks/` está en `apps/web/lib/hooks/use-auth-session.ts`; no existe una carpeta `apps/web/hooks/` en el árbol actual.

### Ejecución local

```bash
cd C:\betmind-ai\apps\web
npm run dev
```

El script `dev` ejecuta `next dev`; los scripts disponibles son `dev`, `build`, `start` y `lint`: `apps/web/package.json:5-10`. El frontend espera el backend en `http://localhost:8000` por defecto (`apps/web/lib/api.ts:6`), por lo que la ejecución funcional local requiere levantar también la API. El build validado genera el frontend en `http://localhost:3000` cuando se usa el servidor de Next.

Hay dos lockfiles en `apps/web`: `package-lock.json` y `pnpm-lock.yaml`. `package-lock.json` refleja `framer-motion` y `jose` declarados (`apps/web/package-lock.json:7-33`); el `pnpm-lock.yaml` contiene además `@vercel/analytics` y `next-themes` en su importer (`apps/web/pnpm-lock.yaml:12-46`), aunque no están en el `package.json` vigente.

### Variables de entorno del frontend

La plantilla está en `apps/web/.env.example:1-3`. Existe un `apps/web/.env.local` en el workspace; sus valores no forman parte de esta auditoría.

| Variable | Uso | Obligatoria |
|---|---|:---:|
| `NEXT_PUBLIC_API_URL` | Base URL de la API FastAPI. Default efectivo: `http://localhost:8000`. | No para local con API en ese puerto; sí para apuntar a otro entorno. |
| `NEXT_PUBLIC_WOMPI_BASE_URL` | Base URL pública de Wompi. Default efectivo: `https://sandbox.wompi.co/v1`. | No por código; debe configurarse al cambiar de entorno. `apps/web/lib/wompi.ts:7`. |
| `NEXT_PUBLIC_WOMPI_PUBLIC_KEY` | Llave pública usada para `/merchants/{key}` y `/tokens/cards`. | Solo para el flujo de activación de pago; sin ella el resto de rutas puede cargar, pero Wompi lanza error. `apps/web/lib/wompi.ts:8,42-46`. |

No hay variables `NEXT_PUBLIC_*` adicionales leídas por el código fuente actual. No hay middleware, proxy, route handlers, `loading.tsx`, `error.tsx` ni `not-found.tsx` propios dentro de `apps/web`.

---

## 2. Inventario completo de rutas

La tabla describe el enforcement real del frontend. “No” en sesión significa que no existe redirect ni guard de ruta; algunas acciones internas pueden requerir token y delegan el rechazo al backend. “Gate visual” significa que el código decide qué renderizar, pero la ruta sigue siendo accesible.

| Path | Requiere sesión | Requiere PRO | Componente principal | Qué hace | Evidencia |
|---|---|---|---|---|---|
| `/` | No | No; solo muestra el estado PRO en navegación | `Page` -> `OnboardingGate` -> `HomePage` -> `HomeView` | Onboarding local en primera visita; después muestra señales, partidos destacados y resumen de tickets. | `app/page.tsx:1-9`; `components/betmind/onboarding.tsx:232-244`; `components/betmind/home-page.tsx:23-93` |
| `/senales` | No | Parcial: las señales cargan sin PRO; guardar y bankroll tienen gates/límites | `SignalsRoute` -> `SignalsPage` -> `TicketCard` | Consulta boletos/señales +EV por ventana temporal y ofrece guardado, copia, compartir y detalle cuantitativo. | `app/senales/page.tsx:1-5`; `components/betmind/signals-page.tsx:51-108`; `ticket-card.tsx:20-53` |
| `/generador` | No | Parcial: perfil gratuito, contador local y modal de límite; no es guard de ruta | `GeneratorRoute` -> `GeneratorPage` -> `TicketGenerator` | Carga ligas/partidos y genera un boleto por perfil, selección, mercados y ligas. | `app/generador/page.tsx:1-5`; `components/betmind/generator-page.tsx:31-90`; `ticket-generator.tsx:182-310` |
| `/historial` | No | No | `HistoryRoute` -> `HistoryPage` | Usuario anónimo lee almacenamiento local; usuario autenticado reclama y lee historial remoto, filtra, pagina y liquida estados. | `app/historial/page.tsx:1-7`; `components/betmind/history-page.tsx:34-159`; `use-ticket-history.ts:8-60` |
| `/partidos` | No | No; la navegación PRO es solo el chip de `TopNav` | `MatchesRoute` -> `MatchesPage` | Consulta cartelera, ligas, fecha, liga seleccionada y filtros de confianza/+EV. | `app/partidos/page.tsx:1-7`; `components/betmind/matches-page.tsx:44-185` |
| `/partidos/[id]` | No | Parcial y client-side: Free recorta/oculta mercados y Bet Builder visualmente | `PartidoDetailPage` -> `MatchDetailContent` | Carga partido, predicción y H2H; muestra Resumen, Pronósticos, Bet Builder y Cara a Cara. | `app/partidos/[id]/page.tsx:1017-1095`; `:950-995` |
| `/bankroll` | No como ruta; sin PRO muestra paywall | Sí en frontend para el contenido funcional: `useProStatus()` decide paywall y carga | `BankrollRoute` -> `BankrollPage` -> `Paywall`, `SetupFlow` o `Dashboard` | Configura capital, perfil de riesgo, evolución, movimientos y ajustes manuales. | `app/bankroll/page.tsx:1-5`; `components/betmind/bankroll-page.tsx:64-77,361-369`; `use-bankroll.ts:7-37` |
| `/planes` | No para consultar; sí para trial, activación y cancelación | Real en operaciones de suscripción vía API; no bloquea la lectura de planes | `PlansPage` | Muestra planes, inicia trial, obtiene aceptación, tokeniza tarjeta, activa, hace polling y cancela. | `app/planes/page.tsx:61-232`; `:237-330`; `components/betmind/wompi-card-form.tsx:21-145` |
| `/cuenta/login` | No; es entrada de sesión | No aplica | `LoginPage` | Hace login JWT, reclama tickets anónimos y redirige a `?redirect=` o `/`. | `app/cuenta/login/page.tsx:10-33` |
| `/cuenta/registro` | No; es alta de cuenta | No aplica | `RegistroPage` | Registra email, contraseña, nombre opcional y confirmación de mayoría de edad solo en cliente. | `app/cuenta/registro/page.tsx:10-46,68-158` |
| `/cuenta/olvide-password` | No | No aplica | `OlvidePasswordPage` | Envía solicitud de recuperación y mantiene respuesta neutral sobre la existencia del email. | `app/cuenta/olvide-password/page.tsx:11-37,40-113` |
| `/cuenta/resetear` | No; depende de `?token=` para ejecutar el reset | No aplica | `ResetearPage` -> `ResetearPageContent` | Valida token presente, contraseña y confirmación; llama al endpoint de reset. | `app/cuenta/resetear/page.tsx:10-63,166-171` |

### Layouts y protección

- `RootLayout` aplica HTML `lang="es"`, fuentes, tema inicial, metadata y `Toaster` a todas las rutas: `apps/web/app/layout.tsx:35-77`.
- `CuentaLayout` solo cambia header, main centrado y footer legal. No comprueba sesión: `apps/web/app/cuenta/layout.tsx:8-34`.
- `AppShell` compone `TopNav`, `main`, footer de juego responsable, navegación móvil, toggle de desarrollo y modal de límite. No usa `redirect`, middleware ni `useAuthSession`: `apps/web/components/betmind/app-shell.tsx:10-27`.
- `TopNav` decide si muestra login o menú de usuario y si muestra chip `PRO` o link a `/planes`: `apps/web/components/betmind/top-nav.tsx:101-141,217-262`.
- La tabla de build también incluye `/_not-found`, pero es salida generada por Next; no existe un archivo fuente `app/not-found.tsx`.

---

## 3. Inventario de componentes clave

Se incluyen todos los archivos de `components/betmind/` de más de aproximadamente 100 líneas y los componentes de menor tamaño que participan directamente en los flujos principales.

| Componente | Tamaño aproximado | Función real | Dependencias principales |
|---|---:|---|---|
| `app-shell.tsx` | 29 líneas | Layout común de rutas de producto; agrega navegación, footer, toggle dev y modal PRO. | `TopNav`, `BottomNav`, `ResponsibleGamingFooter`, `DevProToggle`, `ProLimitModalHost`. |
| `top-nav.tsx` | 281 | Navegación desktop/móvil, tema, sesión, logout, chip PRO y contador de ligas. | `useAuthSession`, `useProStatus`, `lib/auth`, `lib/theme`, `Button`, `Link`. También exporta `BottomNav`. |
| `onboarding.tsx` | 244 | Gate de primera visita por `localStorage`, tres slides, navegación por botones y swipe táctil. | `betmind_onboarding_seen`, Lucide y estado React. |
| `home-page.tsx` | 94 | Orquesta dos fetches independientes de tickets y partidos y entrega loading/error/retry a la vista. | `fetchTickets`, `fetchMatches`, `AppShell`, `HomeView`. |
| `home.tsx` | 181 | Dashboard de bienvenida, resumen de historial, top 3 señales, top 3 partidos y CTA al generador. | `useAuthSession`, `useTicketHistory`, `summarizeTrackedTickets`, `StatDisclaimer`. |
| `signals-page.tsx` | 109 | Consulta señales por fecha, renderiza grid, empty/error/loading y `TicketCard`. | `fetchTickets`, `DateSelector`, `RouteError`, `TicketCard`. |
| `matches-page.tsx` | 185 | Consulta cartelera y ligas; sincroniza fecha/liga en query string; filtra y agrupa por liga. | `fetchMatches`, `fetchLeagues`, `LeagueSidebar`, `LeagueAccordion`, `DateSelector`, `RouteError`. |
| `league-sidebar.tsx` | 187 | Agrupa ligas en Big 5, Sudamérica, UEFA y otras; oculta las de cero partidos; permite seleccionar liga. | `resolveLeague`, `LeagueLogo`, datos de partidos y `LeagueData`. |
| `league-accordion.tsx` | 77 | Acordeón por competición con contador, estado en vivo y lista de `MatchCard`. | `resolveLeague`, `LeagueLogo`, `MatchCard`. |
| `match-card.tsx` | 233 | Enlace a detalle; estado de partido, copa, score, Poisson mini y mejor oportunidad 1X2/mercados básicos. | `buildModel`, `marketRows`, `bestOpportunity`, `PoissonMiniChart`, `TeamLogo`, `Card`. |
| `poisson-mini-chart.tsx` | 93 | Histograma SVG de distribución de goles local/visitante. | `goalDistribution`, tokens `--home-team` y `--away-team`. |
| `generator-page.tsx` | 91 | Carga partidos/ligas y mantiene contador local de generaciones Free. | `fetchMatches`, `fetchLeagues`, `useProStatus`, `TicketGenerator`, `RouteSkeleton`, `RouteError`. |
| `ticket-generator.tsx` | 853 | Configuración de patas, perfil, mercados, ligas, generación automática, límite Free, sustitución, stake, guardado y exportación. | `fetchTickets`, `TicketLeg`, `useBankroll`, `StakeConfirmDialog`, `addToTracking`, `shareOrDownloadTicket`. |
| `ticket-card.tsx` | 156 | Tarjeta de señal autogenerada con odds, EV, patas, stake, guardado, copia y compartir. | `useProStatus`, `useBankroll`, `TicketLeg`, `addToTracking`, `StakeConfirmDialog`. |
| `ticket-leg.tsx` | 143 | Fila de selección; badge EV abre ficha cuantitativa por hover/click; permite rotar pata. | `formatters`, `Link /bankroll`, datos de `Bankroll` y `TicketLegData`. |
| `stake-confirm-dialog.tsx` | 97 | Confirma stake en COP antes de persistir un ticket PRO. | `Dialog`, `Button`, `parseCOPInput`, `Bankroll`, `Ticket`. |
| `tracking-panel.tsx` | 313 | Implementa panel legacy de ledger, persistencia local/remota, claim, polling y cambio de estado. El componente visual no está montado actualmente. | `fetchTicketHistory`, `saveTicket`, `updateTicketStatus`, `lib/tracking`, `sonner`. Sus funciones `addToTracking` y `claimPendingTickets` sí se importan externamente. |
| `history-page.tsx` | 159 | Historial actual con filtros y paginación en URL, métricas, status, eliminación local y retry. | `useAuthSession`, `useTicketHistory`, `updateTicketStatus`, `lib/tracking`, `AppShell`. |
| `use-ticket-history.ts` | 61 | Carga historial remoto autenticado o local anónimo; reclama tickets y escucha eventos de sincronización. | `fetchTicketHistory`, `claimPendingTickets`, `loadTrackedTickets`. |
| `bankroll-page.tsx` | 370 | Paywall, configuración de capital, selección de riesgo, gráfico SVG, ledger y ajustes. | `useProStatus`, `useBankroll`, `lib/bankroll`, `Dialog`, `Button`. |
| `use-bankroll.ts` | 38 | Hook de carga/error/reload del bankroll cuando el gate está habilitado. | `getBankroll` de `lib/bankroll`. |
| `match-tab-bar.tsx` | 49 | Tabs locales del detalle: Resumen, Pronósticos, Bet Builder y Cara a Cara. | Lucide y estado controlado desde `page.tsx`. |
| `tactical-panel.tsx` | 71 | Memorándum cuantitativo: metadata, confianza, xG, ritmo y narrativas si llegan en props. | `Match`, `TacticalFactor`, `formatters`, Lucide. |
| `bet-builder-cards.tsx` | 15 líneas físicas, JSX concentrado en una línea | Renderiza perfiles correlacionados, selecciones, cuota y probabilidad. Recibe datos; no llama a persistencia. | `Link2`; `BetBuilderProfile`. |
| `wompi-card-form.tsx` | 145 | Carga aceptaciones, recoge tarjeta, valida checks, llama tokenización y devuelve tokens al plan. | `fetchWompiAcceptance`, `tokenizeCard`, `jose` indirectamente. |
| `pro-limit-modal.tsx` | 52 | Escucha evento de límite Free y abre CTA a planes. | `PRO_LIMIT_REACHED_EVENT`, `Link`. |
| `dev-pro-toggle.tsx` | 30 | Toggle visible fuera de producción para escribir el flag local de PRO. | `isProUser`, `setDevProFlag`. |
| `route-states.tsx` | 23 | Estado de error con retry y skeleton genérico para rutas. | Lucide. |
| `date-selector.tsx` | 77 | Selector `today/tomorrow/all` y formato de fecha COT. | `Intl.DateTimeFormat`. |
| `league-logo.tsx` | 55 | Imagen de liga con fallback de iniciales. El parámetro `flag` se recibe pero se ignora. | `<img>`, `cn`. |
| `stat-disclaimer.tsx` | 13 | Texto legal estadístico reutilizable. | `lib/disclaimers`. |
| `responsible-gaming-footer.tsx` | 12 | Footer legal y enlace externo a Coljuegos. | HTML y enlace externo. |

La implementación activa de escudos es `components/ui/team-logo.tsx:85-135`, no hay un `components/betmind/team-logo.tsx` en el árbol actual. `TeamLogo` tiene tres tiers: URL del backend, CDN `media.api-sports.io` y escudo SVG con iniciales.

### Componentes de UI base

- `components/ui/button.tsx:1-58`: wrapper de `@base-ui/react/button` con variantes y tamaños.
- `components/ui/dialog.tsx:1-160`: portal, backdrop, popup, título, descripción y footer sobre `@base-ui/react/dialog`.
- `components/ui/card.tsx:1-103`: contenedor y subcomponentes Card.
- `components/ui/team-logo.tsx:1-135`: logo activo de equipos.
- `components/ui/sonner.tsx:1-46`: wrapper global de notificaciones.
- `components/ui/avatar.tsx:1-109`, `separator.tsx:1-25` y `table.tsx:1-116` existen, pero no tienen imports desde componentes de producto en el árbol actual. Son primitivas sin consumidor detectado.

### Huérfanos y código muerto conocido

| Ubicación | Estado observado |
|---|---|
| `components/betmind/market-table.tsx:27-29` | El componente está definido y se importa en `app/partidos/[id]/page.tsx:40`, pero no se renderiza; el chequeo `noUnusedLocals` marca también el import. El detalle usa una implementación inline de mercados. |
| `components/betmind/tracking-panel.tsx:189-313` | `TrackingPanel` no tiene consumidores JSX. El módulo sigue activo porque `addToTracking` se importa en `ticket-card.tsx:15` y `ticket-generator.tsx:24`, y `claimPendingTickets` se reexporta para login/registro. |
| `app/partidos/[id]/page.tsx:140-149` | `EmptyCard` está definido y no se usa. |
| `app/partidos/[id]/page.tsx:371` y `:788` | Parámetro `model` declarado pero no utilizado en `ConfidenceBar` y `H2HTab`. |
| `components/betmind/ticket-generator.tsx:93-120` | `DISPLAY_MARKET_KEYWORDS` y `filterLegsByCategory` están definidos, pero el render usa directamente `ticket.legs.slice(...)`. |
| `components/betmind/ticket-generator.tsx:139-176` | `GeneratorLeg` está definido y no se renderiza; el componente activo es `TicketLeg`. |
| `components/betmind/ticket-generator.tsx:183-194` | La prop `matches` se recibe en `TicketGenerator`, pero no se usa en el cuerpo. |
| `components/betmind/ticket-generator.tsx:185-191` | La prop `onTrack` existe; no hay consumidor que la pase desde las rutas actuales. |
| `components/betmind/league-accordion.tsx:3` | Import de React sin uso. |
| `components/ui/team-logo.tsx:14` | Parámetro `url` de `cdnutf` no se utiliza. |
| `lib/api.ts:1` | `TacticalFactor` y `MarketOdds` se importan como tipos y no se usan. |
| `lib/betmind.ts:9-16,225-230` | `League`, `pct` y `signed` no tienen referencias externas aparentes en el árbol actual. |
| `package.json:15` | `framer-motion` está declarado sin importaciones. |
| `patch_ui.py:4-6` | Script de parche que apunta a `components/betmind/match-modal.tsx`, archivo que no existe actualmente. |

---

## 4. Manejo de estado y datos

### Sesión

- El token propio se guarda como JSON en `localStorage['betmind_access_token']`: `apps/web/lib/auth.ts:18-20,39-47`.
- `hasSession()` solo comprueba la presencia de esa clave; no valida expiración ni estructura antes de devolver `true`: `apps/web/lib/auth.ts:50-53`.
- `useAuthSession()` mantiene `user`, `isLoading` y `refresh`; al montar y al recibir `betmind:auth-changed` llama `GET /api/v1/users/me`: `apps/web/lib/hooks/use-auth-session.ts:6-29`.
- `fetchMe()` limpia el token solo ante `401`; si hay error de red, el hook conserva el `user` anterior y no expone un estado de error: `apps/web/lib/auth.ts:123-143`; `apps/web/lib/hooks/use-auth-session.ts:10-20`.
- No existe un provider global de sesión. Cada instancia de `useAuthSession()` ejecuta su propio ciclo de carga.
- `apiFetch()` también busca claves `sb-*-auth-token` además de `betmind_access_token`: `apps/web/lib/api.ts:18-33`. `hasSession()`, `fetchMe()` y `clearToken()` solo operan sobre `betmind_access_token`: `apps/web/lib/auth.ts:44-53,123-135`. Por tanto, puede haber requests con Bearer proveniente de una clave `sb-*` mientras la UI considera que no hay sesión propia.

### PRO y fuente de verdad

La fuente declarada para usuarios autenticados es `user.is_pro` obtenido de `GET /api/v1/users/me`:

- `UserMe` define `is_pro` y `pro_expires_at`: `apps/web/lib/auth.ts:28-35`.
- `fetchMe()` escribe `data.is_pro` en el cache de módulo `cachedIsPro`: `apps/web/lib/auth.ts:142,148-155`.
- `useProStatus` es solo un alias de compatibilidad hacia `useIsPro`: `apps/web/components/betmind/use-pro-status.ts:3-7`.
- `useIsPro()` devuelve `false` mientras `useAuthSession` está cargando, `user.is_pro` si hay usuario y el flag local si no hay sesión: `apps/web/lib/subscription.ts:45-67`.
- `isProUser()` es la consulta síncrona usada por `addToTracking`. Con sesión usa `cachedIsPro ?? false`; sin sesión lee `betmind_dev_is_pro`: `apps/web/lib/subscription.ts:29-37`.
- `clearToken()` limpia `cachedIsPro`: `apps/web/lib/auth.ts:44-48`. `storeToken()` no limpia el cache antes de iniciar una nueva sesión: `apps/web/lib/auth.ts:39-42`.
- El flag `betmind_dev_is_pro` se sincroniza por evento custom y `storage` solo en instancias sin sesión: `apps/web/lib/subscription.ts:49-73`.
- `apiFetch()` envía `X-Betmind-Dev-Pro: 1` si no encuentra token y el flag vale `true`: `apps/web/lib/api.ts:44-55`. El botón que lo escribe se oculta con `NODE_ENV === 'production'`, pero la lógica de lectura no comprueba `NODE_ENV`: `apps/web/components/betmind/dev-pro-toggle.tsx:11-20`.
- No hay TTL ni asociación de `cachedIsPro` con el usuario actual. La sincronización de auth y PRO entre pestañas usa el evento custom de la misma ventana y listeners parciales; `useAuthSession` no escucha el evento `storage`: `apps/web/lib/hooks/use-auth-session.ts:23-27`.

El endpoint `/api/v1/subscriptions/me` se usa para pintar y operar la pantalla de planes, no como fuente directa de los gates de PRO: `apps/web/app/planes/page.tsx:75-101`; `apps/web/lib/subscriptions.ts:40-42`.

### Backend vía fetch

`apiFetch()` centraliza la mayoría de los requests, añade Bearer si encuentra token, aplica timeout de 12 segundos y normaliza errores HTTP, timeout y red: `apps/web/lib/api.ts:6-7,35-86`. No hay retry ni cache HTTP, React cache, SWR o React Query.

| Grupo | Requests | Consumidores |
|---|---|---|
| Auth directo | `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `POST /api/v1/auth/forgot-password`, `POST /api/v1/auth/reset-password`, `GET /api/v1/users/me` | `lib/auth.ts:68-143`; páginas de cuenta y `useAuthSession`. Estos `fetch` no usan el timeout común. |
| Tickets | `POST /api/v1/tickets/save`, `POST /api/v1/tickets/claim`, `GET /api/v1/tickets/history`, `PATCH /api/v1/tickets/{id}/status`, `POST /api/v1/tickets/generate` | `lib/api.ts:216-296`; señales, generador, historial, tracking, login y registro. |
| Cartelera | `GET /api/v1/matches/?...`, `GET /api/v1/leagues/` | `lib/api.ts:459-599`; Home, `MatchesPage` y `GeneratorPage`. |
| Detalle | `GET /api/v1/matches/{id}`, `GET /api/v1/predictions/{id}`, `GET /api/v1/matches/{id}/h2h` | `lib/api.ts:742-807`; `app/partidos/[id]/page.tsx:1029-1032`. |
| Bankroll | `POST /api/v1/bankroll/setup`, `GET /api/v1/bankroll`, `PATCH /api/v1/bankroll`, `POST /api/v1/bankroll/adjust` | `lib/bankroll.ts:65-103`; `BankrollPage`, `TicketGenerator` y cada `TicketCard` PRO. |
| Suscripción | `POST /api/v1/subscriptions/trial`, `GET /api/v1/subscriptions/me`, `POST /api/v1/subscriptions/activate`, `POST /api/v1/subscriptions/cancel` | `lib/subscriptions.ts:30-64`; `app/planes/page.tsx:124-232`. No existe wrapper frontend para `/api/v1/subscriptions/refund`. |
| Llave Wompi | `GET /api/v1/subscriptions/wompi-tokenization-key` | `lib/wompi.ts:73-79`. |

`fetchMatchPrediction()` hace en paralelo match y prediction. Si falla prediction pero match responde, retorna un `EnrichedMatch` con probabilidades, EV, análisis y Bet Builder vacíos/cero en lugar de retornar error: `apps/web/lib/api.ts:782-807`.

### `localStorage`, cookie y persistencia local

| Clave | Tipo de dato / uso | Evidencia |
|---|---|---|
| `betmind_access_token` | JSON con `access_token`; JWT propio de sesión. | `apps/web/lib/auth.ts:19,39-53`. |
| `sb-*-auth-token` | Patrón de claves que `apiFetch` inspecciona; el frontend actual no las escribe ni elimina. | `apps/web/lib/api.ts:20-31`. |
| `betmind_dev_is_pro` | String `true/false`; simulación de PRO sin sesión para desarrollo. | `apps/web/lib/subscription.ts:19,29-37,70-73`. |
| `betmind_tracked_tickets` | Array `TrackedTicket`; fallback local y cache local de tickets remotos. | `apps/web/lib/tracking.ts:19,49-65`; `components/betmind/tracking-panel.tsx:35-93`. |
| `betmind_daily_generations` | JSON `{date,count}` en fecha COT; contador Free de generaciones explícitas. | `apps/web/components/betmind/generator-page.tsx:15-29,45-55`. |
| `betmind_onboarding_seen` | String `true`; oculta el onboarding después de completarlo. | `apps/web/components/betmind/onboarding.tsx:8,120-123,232-243`. |
| `betmind_theme` | `light`, `dark` o `system`; preferencia visual. | `apps/web/lib/theme.ts:3,6-14`; lectura temprana en `app/layout.tsx:6-16`. |

El tema también se replica en la cookie `betmind_theme` para persistencia del navegador: `apps/web/lib/theme.ts:12-15`. No hay usos de `sessionStorage`.

Comportamiento del tracking local/remoto:

- `addToTracking()` aplica un límite local de cinco entradas Free antes de llamar al backend: `apps/web/components/betmind/tracking-panel.tsx:46-54`.
- Si `POST /tickets/save` responde correctamente, guarda una copia local marcada `remote: true`; si falla por cualquier motivo, crea una entrada local `remote: false` y retorna `saved: true`: `apps/web/components/betmind/tracking-panel.tsx:56-93`. El error remoto no se comunica a la UI como error de guardado.
- La copia local se recorta a diez entradas tanto para entradas remotas como locales: `apps/web/components/betmind/tracking-panel.tsx:71-92`.
- `claimPendingTickets()` solo intenta reclamar entradas locales remotas con ID numérico: `apps/web/lib/tracking.ts:36-46`.
- La eliminación del historial actual llama `saveTrackedTickets()` y no tiene request de borrado remoto; una nueva carga remota puede volver a mostrar el ticket: `apps/web/components/betmind/history-page.tsx:88-92`.
- El contador diario se incrementa antes de saber si la generación finalizó correctamente: `apps/web/components/betmind/generator-page.tsx:45-55`.
- Las ejecuciones automáticas de `TicketGenerator` no llaman al contador; solo lo hacen cuando `isExplicitGenerate.current` fue marcado por el botón de regenerar: `apps/web/components/betmind/ticket-generator.tsx:213-219,272-278,617-625`.

### Re-fetching y requests redundantes

No existe estado compartido para sesión, PRO, partidos, ligas, historial o bankroll. El frontend contiene los siguientes consumidores independientes:

| Datos | Consumidores independientes | Comportamiento |
|---|---|---|
| `/matches/` | `HomePage`, `MatchesPage`, `GeneratorPage` | Cada ruta llama `fetchMatches()` en su propio `useEffect`: `home-page.tsx:56-72`, `matches-page.tsx:63-81`, `generator-page.tsx:58-77`. No hay cache ni dedupe de requests. |
| `/leagues/` | `MatchesPage`, `GeneratorPage` | Cada componente llama `fetchLeagues()` por separado: `matches-page.tsx:83-91`, `generator-page.tsx:63-77`. Si falla, ambos manejan el resultado de forma distinta. |
| `/users/me` | `SessionControl`, `TopNav` vía `useProStatus`, y hooks adicionales de cada ruta | Cada `useAuthSession()` dispara `fetchMe()`. En señales, cada `TicketCard` crea una instancia de `useProStatus()`: `ticket-card.tsx:20-25`. |
| `/bankroll` | `BankrollPage`, `TicketGenerator`, cada `TicketCard` | `useBankroll(isPro)` se monta en cada consumidor: `bankroll-page.tsx:361-364`, `ticket-generator.tsx:205-211`, `ticket-card.tsx:20-25`. Tres señales PRO pueden provocar tres GET de bankroll. |
| Historial | `HomeView`, `HistoryPage`, y `TrackingPanel` si se vuelve a montar | `HomeView` y `HistoryPage` usan instancias distintas de `useTicketHistory`; `TrackingPanel` mantiene además polling de 30 segundos: `tracking-panel.tsx:189-231`. |
| Planes / auth | `PlansPage` emite `betmind:auth-changed` y además llama `refresh()` después de trial, activación y cancelación | Esto dispara el listener del hook y la llamada explícita: `app/planes/page.tsx:140-142,194-195,227-230`; `use-auth-session.ts:23-27`. |
| Detalle | `MatchDetailContent` usa un `useProStatus`; `QuantMarkets` monta otro cuando se activa esa tab | Puede haber una segunda consulta de `/users/me` al cambiar a Pronósticos: `app/partidos/[id]/page.tsx:492-499,950-979`. |

`dedupeMatches()` elimina duplicados dentro de la respuesta ya recibida, usando nombres normalizados y una ventana de dos horas: `apps/web/lib/api.ts:474-575`. No deduplica requests HTTP. Por tanto, el patrón observado por backend de la misma consulta de partidos repetida en una sesión corta tiene un origen concreto en este frontend, aunque la atribución exacta de cada línea de log requiere correlacionar timestamps.

Hay también desajustes de contrato visibles en el cliente:

- `TicketGenerator` recibe `matches`, pero genera mediante `POST /tickets/generate` sin leer esa prop: `apps/web/components/betmind/ticket-generator.tsx:182-194,282-310`.
- El generador carga partidos con `fetchMatches('today')`, pero la generación no envía `date_filter`: `generator-page.tsx:63`; `ticket-generator.tsx:284-290`.
- Los presets de cuota actualizan `oddsMin/oddsMax` y el indicador de rango, pero esos valores no se envían en `fetchTickets()`: `ticket-generator.tsx:582-614`; `lib/api.ts:261-280`.
- Si se desactivan todos los mercados, `fetchTickets()` omite `markets` porque solo envía arrays con `.length`: `lib/api.ts:273-280`; la UI puede representar “ningún mercado” mientras el backend interpreta ausencia como default.
- El adapter no conserva `total_markets` aunque la UI promete `56`; `QuantMarkets` imprime `markets.length/56`: `lib/api.ts:630-705`; `app/partidos/[id]/page.tsx:492-500`.
- `mapBackendMatch()` fija `signal: 'WEAK'` y `pros`, `cons`, `keyRisk` vacíos: `lib/api.ts:448-452`. Los bloques que consumen esos campos no pueden mostrar señales enriquecidas desde ese mapeo.

---

## 5. Integraciones externas del lado del cliente

### Wompi

La integración vive en `apps/web/lib/wompi.ts` y `apps/web/components/betmind/wompi-card-form.tsx`.

| Paso | Implementación | Evidencia |
|---|---|---|
| Configuración | `NEXT_PUBLIC_WOMPI_BASE_URL` con fallback sandbox y `NEXT_PUBLIC_WOMPI_PUBLIC_KEY`. | `lib/wompi.ts:7-8`. |
| Aceptaciones | `GET {WOMPI_BASE_URL}/merchants/{publicKey}` con Bearer de la llave pública. | `lib/wompi.ts:61-71`; formulario: `wompi-card-form.tsx:34-49`. |
| Llave de tokenización | Se obtiene del backend autenticado mediante `/subscriptions/wompi-tokenization-key`. | `lib/wompi.ts:73-79`. |
| JWE | `EncryptJWT` con la tarjeta como payload; llave SPKI RSA; header `RSA-OAEP-256` + `A256GCM`. | `lib/wompi.ts:81-86`. |
| Tokenización | `POST {WOMPI_BASE_URL}/tokens/cards` con `{payload}` y la llave pública. | `lib/wompi.ts:88-113`. |
| Entrega al backend | `WompiCardForm` devuelve `card_token`, `acceptance_token` y `accept_personal_auth` a `PlansPage`, que llama `/subscriptions/activate`. | `wompi-card-form.tsx:61-85`; `app/planes/page.tsx:158-178`; `lib/subscriptions.ts:44-59`. |
| Datos privados | No se incluye llave privada en el bundle; el backend entrega la llave de tokenización y Wompi recibe la tarjeta cifrada. | `lib/wompi.ts:73-113`. |

El formulario usa `autoComplete` de tarjeta y checks de aceptación, pero la validación cliente de número, Luhn, mes, expiración y año es mínima: `components/betmind/wompi-card-form.tsx:97-117`. No hay `AbortController` ni timeout en los dos `fetch` directos a Wompi: `lib/wompi.ts:61-69,95-106`. La aceptación se carga una vez y no tiene control de retry específico: `wompi-card-form.tsx:34-49`.

### Otras integraciones y SDKs

- `@base-ui/react` se usa para Button, Dialog, Avatar y Separator: `components/ui/*.tsx`.
- `sonner` se usa para toasts globales y feedback de guardado, pagos y bankroll: `components/ui/sonner.tsx:6-43`.
- `jose` solo se importa en Wompi: `lib/wompi.ts:3`.
- Lucide es la única librería de iconografía usada en el código de producto.
- Los gráficos son SVG manuales: `components/betmind/poisson-mini-chart.tsx:21-93`, `components/betmind/bankroll-page.tsx:185-210`, radar en `app/partidos/[id]/page.tsx:751-765`.
- La exportación de tickets usa Canvas, Web Share API y descarga de Blob; no usa `html-to-image`, SDK de Wompi ni librería de charts: `apps/web/lib/ticket-export.ts:48-132`.
- Las imágenes se renderizan con `<img>` en `LeagueLogo` y `TeamLogo`, no con `next/image`: `components/betmind/league-logo.tsx:36-52`; `components/ui/team-logo.tsx:102-129`. `next.config.mjs` declara `remotePatterns`, pero además `unoptimized: true` y `domains` deprecated: `apps/web/next.config.mjs:3-20`.
- `next/font/google` carga Inter, Playfair Display e IBM Plex Mono: `app/layout.tsx:2,19-33`.
- `responsible-gaming-footer.tsx:5-8` enlaza externamente a `https://www.coljuegos.gov.co`.
- No hay imports de `recharts`, `chart.js`, `d3`, `visx`, `@vercel/analytics` ni `next-themes` en `apps/web`. Los dos últimos aparecen solo en `pnpm-lock.yaml:17-34,713-713,1543-1543`.

---

## 6. Sistema de diseño y temas

### Tokens vigentes

El sistema semántico está definido en `apps/web/app/globals.css:7-55` y tiene valores separados para `:root` claro y `.dark` oscuro:

| Grupo | Claro | Oscuro | Evidencia |
|---|---|---|---|
| Fondo/superficies | `--background`, `--surface`, `--surface-raised`, `--surface-inset`, `--card`, `--popover` | Valores equivalentes oscuros | `globals.css:60-65,105-110`. |
| Identidad | `--brand`, `--primary`, `--primary-foreground` | `brand` y `primary` son ambos `#8FE3A8` | `globals.css:68-75,113-118`. |
| Estados | `--positive`, `--warning`, `--negative` | Menta, ámbar y rojo oscuros | `globals.css:73-76,116-118`. |
| Equipos | `--home-team`, `--away-team` | Índigo y rosa | `globals.css:77-78,119-120`. |
| Tipografía | Inter, Playfair, IBM Plex Mono | mismas familias | `app/layout.tsx:19-33`; `globals.css:7-10`. |

El tema se inicializa antes de hidratar leyendo `betmind_theme`, aplicando clase `dark` y `colorScheme`: `app/layout.tsx:6-16`. `ThemeControl` permite `light`, `dark` y `system`: `components/betmind/top-nav.tsx:23-83`. El CSS también contiene reduced motion, touch targets de 44px para pointer coarse y `overscroll-behavior` para diálogos: `globals.css:283-335`.

### Hexes y colores fuera de tokens

No se detectó una nueva paleta de hexes dentro de los componentes de producto; la mayoría usa clases semánticas (`bg-card`, `text-positive`, `bg-surface`, etc.). Los valores hardcodeados fuera de la definición central son:

- `app/layout.tsx:60`: `themeColor: '#0A0D10'`, fijo al dark aunque existe tema claro.
- `lib/ticket-export.ts:6-10`: `EXPORT_PALETTE` repite `#0A0D10`, `#8FE3A8` y `#F1F5F4`; el PNG siempre usa la paleta oscura, independientemente del tema activo.
- `globals.css:176` y `components/betmind/tactical-panel.tsx:58`: sombras con `rgba(255,255,255,...)` fuera de tokens.
- Hay utilidades de blanco/negro en overlays y detalles, por ejemplo `ring-white/5` en `ticket-card.tsx:62`, `bg-white/10` en `league-logo.tsx:39`, `bg-black/60` en overlays de `matches-page.tsx:152` y skeleton/error del detalle en `page.tsx:1004-1008,1075-1088`. No son hexes nuevos, pero no reaccionan a tokens claros de la misma forma.

El detalle de partido usa algunas variables CSS directamente (`bg-[var(--surface)]`, `var(--surface-raised)`, `var(--surface-inset)`) en lugar de las clases semánticas habituales: `app/partidos/[id]/page.tsx:429-433,456-472,774,922-926`.

### Inconsistencias visuales documentadas

- El documento anterior `BETMIND_UI_UX_FLOW.md:31` describe un producto 100% oscuro y un `themeColor` distinto; el código vigente soporta claro, oscuro y sistema, con `themeColor` oscuro fijo: `app/layout.tsx:58-60`, `globals.css:57-142`.
- `components/ui/sonner.tsx:8-10` fuerza `theme="dark"`; los toasts no siguen automáticamente el tema claro.
- `--brand` y `--primary` son colores distintos en claro pero iguales en oscuro: `globals.css:68-75,113-118`. La UI mezcla `bg-brand` y `bg-primary` para CTAs equivalentes.
- El detalle de partido es la zona con más clases ad hoc, overlays opacos y estilos inline; Home, Señales, Historial y Bankroll usan más sistemáticamente los tokens semánticos.
- `LeagueSidebar` muestra `{cantidad}/26` aunque el total no proviene de un parámetro de backend: `components/betmind/league-sidebar.tsx:143-154`.
- El estado activo de equipo usa `primary`/`warning` en varios lugares, mientras el radar y el mini chart usan `--home-team`/`--away-team`: `globals.css:40-41`; `poisson-mini-chart.tsx:67-76`; `page.tsx:764`.

---

## 7. Vista de Análisis / detalle de partido

### Estructura actual

`apps/web/app/partidos/[id]/page.tsx` tiene 1.095 líneas y concentra carga de datos, tipos locales, builders, layout, tabs, gráficos SVG, gates PRO y estados de página. No reutiliza `AppShell`; crea un header sticky propio: `page.tsx:1017-1095`.

Flujo de datos:

- `fetchMatchPrediction(id)` llama en paralelo `GET /matches/{id}` y `GET /predictions/{id}`: `lib/api.ts:782-789`.
- La página llama en paralelo lógico `fetchMatchPrediction(id)` y `fetchMatchH2H(id)` mediante `Promise.allSettled`: `page.tsx:1025-1032`.
- El partido y la predicción se almacenan juntos en `match` y `enriched`; H2H se guarda aparte: `page.tsx:1019-1021,1035-1041`.
- Si falla la carga del partido, la página muestra `Partido no encontrado`; si falla solo prediction, el adapter puede devolver datos cero y la página continúa como si hubiera detalle: `lib/api.ts:794-804`; `page.tsx:1036-1041`.
- El fallo de H2H no activa el estado de error; se mantiene `h2h = null`: `page.tsx:1035-1036`.
- La pantalla no tiene retry. El error del partido y un error de red se presentan con el mismo texto de “no encontrado”: `page.tsx:1075-1088`.
- Aunque `Promise.allSettled` no convierte H2H en fallo fatal, la página espera a que se resuelvan ambas promesas antes de terminar `loading`: `page.tsx:1027-1049`.

### Cabecera y estado transversal

Antes de las tabs se renderizan:

- `MatchHero`: liga, hora COT, estado, equipos, marcador y probabilidades 1X2 calculadas por `buildModel`: `page.tsx:255-365`.
- `SignalRail`: score de confianza, estado de mercado usando edge 1X2 y completitud de datos: `page.tsx:412-423`.
- `ConfidenceBar`: confianza, riesgo, marcador probable, over/under y headline: `page.tsx:371-410`.
- `MatchTabBar`: cuatro tabs controladas por `activeTab` local: `page.tsx:950-979`; `components/betmind/match-tab-bar.tsx:7-49`.

El tab activo no se refleja en query string ni en URL. `MatchTabBar` genera `aria-controls`, pero los paneles renderizados no tienen los IDs `match-panel-*`, `role="tabpanel"` ni `aria-labelledby`: `components/betmind/match-tab-bar.tsx:27-43`; `app/partidos/[id]/page.tsx:974-992`.

### Tabs

| Tab | Rango principal | Contenido real | Datos/dependencias | Deuda visible |
|---|---:|---|---|---|
| **Resumen & Insights** | `page.tsx:700-745` y helpers `:255-690` | `TacticalPanel`, recomendación principal o protección de capital, barras de probabilidades, top 5 marcadores, corners/tarjetas y `ScouterStats`. | `Match`, modelo frontend, `EnrichedMatch`, `advancedStats`, `refereeProfile`. | Es la tab con mayor superficie de dependencias: su render corto compone varios helpers locales. `TacticalPanel` admite narrativas, pero la página solo le pasa metadata y headline: `page.tsx:718-726`; `tactical-panel.tsx:38-68`. El adapter del match deja `pros`, `cons` y `keyRisk` vacíos: `lib/api.ts:448-452`. |
| **Pronósticos (56M)** | `page.tsx:439-517` | Top 5 de señales, tarjetas modelo/casa, acordeones por grupos de mercado, disclaimer y overlay Free. | `enriched.evAnalysis`, `formatMarketName`, `QuantMarkets`, `MarketAccordion`, `LockedMarkets`. | El número 56 está hardcodeado; `total_markets` no se mapea. Free hace `slice(0, 10)` en cliente; `LockedMarkets` recibe la lista completa del adapter, que puede ya venir recortada por backend. `MarketTable` importado no participa. |
| **Bet Builder** | `page.tsx:980-989`; `bet-builder-cards.tsx:12-15` | PRO muestra `BetBuilderCards`; Free muestra una copia borrosa con CTA a planes. | `detail.betBuilder` proveniente de `EnrichedMatch.betBuilder`; `useProStatus`. | La ruta PRO no renderiza nada si el array está vacío por la condición `length > 0`: `page.tsx:981-983`. El componente de tarjetas solo recibe datos y no llama a persistencia ni a `addToTracking`: `bet-builder-cards.tsx:3-15`. |
| **Cara a Cara** | `page.tsx:785-944`; helpers `:751-783` | Forma reciente, modelo xG, señal/narrativa, referencia H2H, radar SVG, historial de enfrentamientos, porcentaje de goles después del minuto 45 y narrativa parseada. | `MatchH2HData`, `Match`, `MatchDetailData`, `TacticalRadar`, `RadarChart`, `NarrativeBody`. | El cuerpo de `H2HTab` ocupa aproximadamente 160 líneas (`:785-944`) y compone cuatro subbloques; el radar usa defaults y fórmulas heurísticas. El badge fija `Groq · Llama 3.3` aunque el adapter expone `llmModelUsed`: `page.tsx:808-812`; `lib/api.ts:766-770`. |

Por tamaño de bloque, Cara a Cara es la tab individual más extensa; por superficie de dependencias y cantidad de widgets, Resumen & Insights abarca el tramo más grande del archivo (`page.tsx:255-745`). Pronósticos y Builder están más acotados, pero mantienen contratos y gates duplicados dentro de la página.

### Deuda específica del detalle

- `MatchHero` y parte de `ModelProbabilities` recalculan probabilidades con `buildModel()` en lugar de usar todas las probabilidades recibidas en `enriched.probabilities`: `page.tsx:952-960`; `ModelProbabilities` en `:587-618`. Solo `over_2_5` usa el valor de `enriched` cuando existe.
- El modelo frontend usa grid Poisson de `0..9` y no aplica la misma corrección del motor backend; `buildModel` está en `lib/betmind.ts:174-213`.
- `PrimaryRecommendation` presenta `formatEV(best.edge)`, aunque el campo usado es `edge`, no `ev`: `page.tsx:527-529`.
- `CapitalProtectionPanel` fija el texto “0% EV” cuando no se supera el umbral local de 3%, incluso cuando puede haber cuotas ausentes o una ventaja menor al umbral: `page.tsx:425-437`; decisión en `PreviaTab:715-731`.
- `buildDetail()` inicializa `homeRecentForm` y `awayRecentForm` como arrays vacíos y usa defaults `3.5`, `0.2` y `26` para métricas del árbitro: `page.tsx:80-125`. Esos campos no se presentan en la tab Resumen.
- `TacticalPanel` tiene campos de narrativas en su tipo, pero `PreviaTab` no los suministra; la lectura rápida usa `match.summary`, que el adapter construye como `${home} vs ${away} - league`: `tactical-panel.tsx:38-68`; `lib/api.ts:448-452`.
- `TacticalRadar` usa `3.5` como default de tarjetas, deriva córneres de `cornersProb / 10` si no hay stats y usa la misma fricción del árbitro para local y visitante: `page.tsx:767-774`.
- El badge de H2H no refleja `llmModelUsed`; `H2HTab` recibe `model` pero no lo usa: `page.tsx:785-800`.
- `H2HReferencePanel` declara degradación trazable cuando no hay H2H, pero la vista no tiene un estado de loading parcial para ese bloque: `page.tsx:777-783,917-927`.
- El enlace “Volver a Partidos” apunta a `/`, no a `/partidos`, tanto en header como en error: `page.tsx:1057-1063,1081-1087`.
- El header del detalle no incluye el `TopNav`, `ResponsibleGamingFooter`, `BottomNav`, `DevProToggle` ni `ProLimitModalHost` de `AppShell`; utiliza una composición distinta: `page.tsx:1053-1073`.
- La copia Free del detalle es client-side: `evAnalysis` completo llega al navegador antes de `slice(0, 10)` y del blur visual: `page.tsx:492-515,979-986`; `lib/api.ts:758-765`.

---

## 8. Código muerto e inconsistencias conocidas

### TODOs y marcas pendientes

| Archivo | Línea | Texto / estado |
|---|:---:|---|
| `components/betmind/generator-page.tsx` | 32 | `TODO(backend-pagos)`: reemplazar por chequeo real de suscripción. El componente ya usa `useProStatus`, pero el comentario sigue presente. |
| `components/betmind/tracking-panel.tsx` | 50 | `TODO(backend-pagos)`: reemplazar por chequeo real de suscripción en el límite local. |
| `components/betmind/tracking-panel.tsx` | 71, 90 | `TODO(backend-pagos)`: PRO ilimitado cuando exista persistencia backend; el cache local conserva tope técnico de 10. |
| `components/betmind/onboarding.tsx` | 184 | `TODO(auth)`: agregar paso de creación de cuenta cuando exista registro real. El registro ya existe en `app/cuenta/registro/page.tsx`. |
| `app/partidos/[id]/page.tsx` | 495, 961 | Dos `TODO(backend-pagos)` para reemplazar chequeo de suscripción. Ambos bloques ya llaman `useProStatus`. |

No se encontraron `FIXME` ni `HACK` en código fuente de `apps/web`. Las coincidencias de `XXX` están dentro de hashes de lockfiles y no son marcadores de código.

### Inconsistencias de comportamiento y contratos

- `TicketLeg` renderiza `leg.market` directamente (`components/betmind/ticket-leg.tsx:40-42`), mientras `TicketCard` y el generador usan `formatMarketName()` para copia o render auxiliar (`ticket-card.tsx:33-35`; `ticket-generator.tsx:147-158,335-338`). Si el backend entrega una clave técnica en `market_label`, la fila activa puede mostrarla cruda.
- El adapter define campos raw para `player_props_narratives` y `bet_builder_suggestions`, pero el tipo `EnrichedMatch.tacticalAnalysis` no los conserva al mapear: `lib/api.ts:616-628,686-692,771-778`.
- La UI presenta `56M` y `10 de 56` en varios lugares, pero no conserva el total del backend: `app/partidos/[id]/page.tsx:499,511`; `app/planes/page.tsx:24-30`.
- La pantalla de planes promete devolución de dinero dentro de siete días (`app/planes/page.tsx:304-305`), pero no hay función frontend para refund y la ruta no se invoca desde la UI: `lib/subscriptions.ts:36-64`.
- La confirmación de mayoría de edad se mantiene en estado React y no se envía a `register`: `app/cuenta/registro/page.tsx:15,25-27,34-40`; `lib/auth.ts:68-81`.
- El botón de guardar de `BetBuilderCards` no tiene persistencia de ticket ni request de backend; el componente recibe únicamente perfiles y renderiza sus datos: `components/betmind/bet-builder-cards.tsx:5-15`.
- `TicketCard` y `TicketGenerator` comparten lógica de stake, sustitución, guardado y exportación, pero no comparten un componente de flujo superior: `ticket-card.tsx:20-60`; `ticket-generator.tsx:349-373,421-431`.
- `TrackingPanel` mantiene una implementación de historial distinta de `HistoryPage`; una no está montada y la otra es la ruta activa: `tracking-panel.tsx:189-313`; `history-page.tsx:34-159`.

### Divergencias con documentación y prompts anteriores

Estas diferencias se verifican contra documentación versionada en el mismo workspace, no contra una intención inferida:

| Documento anterior | Afirmación | Estado del código actual |
|---|---|---|
| `BETMIND_UI_UX_FLOW.md:141-148` | Exactamente dos rutas físicas; no existe `/partidos`; cartelera y escáner son tabs del dashboard. | Hay 12 `page.tsx` físicos, incluyendo `/partidos`, `/senales`, `/generador`, `/historial`, `/bankroll` y `/planes`. La ruta `/partidos` existe en `app/partidos/page.tsx`. |
| `BETMIND_UI_UX_FLOW.md:152-165` | Navegación de tres tabs `Boletos`, `Partidos`, `Escáner` y un `Dashboard`. | `TopNav` tiene cuatro links: `Señales`, `Partidos`, `Historial`, `Bankroll`: `components/betmind/top-nav.tsx:16-21`. No existe `components/betmind/dashboard.tsx` en el árbol actual. |
| `BETMIND_UI_UX_FLOW.md:31,119` | Tema 100% oscuro y `colorScheme` oscuro forzado. | El código implementa `light`, `dark` y `system`, y `globals.css` define ambos temas: `app/layout.tsx:58-60`; `components/betmind/top-nav.tsx:23-83`; `globals.css:57-142`. |
| `BETMIND_UI_UX_FLOW.md:294-297,432-443` | `TrackingPanel` forma parte del dashboard y su panel aparece bajo los boletos. | `HomeView` solo usa `useTicketHistory` para el resumen; no renderiza `TrackingPanel`: `components/betmind/home.tsx:109-117,135-161`. El componente está huérfano como UI. |
| `BETMIND_UI_UX_FLOW.md:313,565-573` | Existe un ScannerEmptyState y varios componentes legacy listados como presentes. | No hay `scanner-empty-state.tsx` ni esos archivos en el árbol actual de `components/betmind`. El archivo de flujo quedó desactualizado respecto a la purga/migración. |
| `BETMIND_UI_UX_FLOW.md:358-360,505-535` | Contrato de 56 mercados y `total_markets`/narrativas completas disponibles para UI. | El adapter vigente no tipa ni conserva `total_markets`; la UI hardcodea 56. Tampoco conserva todos los campos de narrativas en `EnrichedMatch`: `lib/api.ts:630-705,771-778`. |
| `PROJECT_LOG.md:4550-4553` | `package-lock.json` fue eliminado porque el proyecto usa pnpm. | `apps/web/package-lock.json` existe y contiene dependencias npm; también existe `pnpm-lock.yaml`. |
| `BETMIND_UI_UX_FLOW.md:99-115` | Ningún mercado se muestra crudo porque todo pasa por `formatMarketName()`. | `TicketLeg` muestra `leg.market` directamente; no llama al formatter en el render de la fila: `components/betmind/ticket-leg.tsx:40-42`. |

---

## 9. Manejo de errores y estados de carga

### Cobertura por bloque

| Bloque | Loading | Error | Retry | Estado real / regresión observada |
|---|---|---|---|---|
| Home - señales | `ticketsLoading` y skeleton propio | `ticketsError` | `ticketRetryKey` | Independiente del bloque de partidos: `home-page.tsx:25-54`; `home.tsx:152-162`. |
| Home - partidos | `matchesLoading` y skeleton propio | `matchesError` | `matchesRetryKey` | Independiente de señales: `home-page.tsx:26-32,56-72`; `home.tsx:164-170`. |
| Home - resumen | `summaryLoading` desde `useTicketHistory` | El error del hook no se muestra en Home | No visible en Home | Un fallo remoto del historial puede dejar el resumen en loading/vacío sin mensaje de error: `home.tsx:109-150`; `use-ticket-history.ts:27-35`. |
| Señales | `loading` + `TicketLoadingGrid` | `RouteError` o empty | `retryKey` | Tiene estados completos para su request principal: `signals-page.tsx:51-105`. Cada `TicketCard` hace requests adicionales de auth/bankroll. |
| Partidos | `loading` + `MatchesSkeleton` | `RouteError` para partidos | `retryKey` | El request de ligas no tiene error independiente; cualquier fallo de ligas se transforma en `[]`: `matches-page.tsx:83-91`. |
| Generador - cartelera | `loading` + `RouteSkeleton` | Error solo si falla `fetchMatches` | Retry de la carga conjunta | Si falla `fetchLeagues` pero partidos responden, se sigue con ligas vacías sin mostrar error: `generator-page.tsx:58-77`. |
| Generador - ticket | `loading` y skeleton de patas | Mensaje genérico interno | No hay retry específico; regenerar vuelve a generar y puede consumir el límite | `TicketGenerator` captura el error y solo pone `error=true`: `ticket-generator.tsx:282-301,736-751`. |
| Historial | Skeleton durante `useTicketHistory` | Error visible con mensaje y retry | `reload()` | Historial remoto tiene flujo propio; parseo local fallido se convierte silenciosamente en `[]`: `history-page.tsx:102-112`; `lib/tracking.ts:49-57`. |
| Bankroll | Skeleton de pantalla | Error visible + mensaje | `reload()` | Setup, cambio de riesgo y ajuste manejan errores por separado, sin retry automático: `bankroll-page.tsx:98-113,262-297,361-369`. |
| Planes / suscripción | Estado `subscriptionLoading`, estados de pago | `pageError`, rechazo y timeout | No hay retry específico de aceptación; el polling aborta ante primer error | `app/planes/page.tsx:75-101,158-216`. |
| Wompi | `loadingAcceptance`, `tokenizing` | `role=alert` | Se puede reenviar tokenización; la aceptación no tiene botón de retry | `wompi-card-form.tsx:30-49,61-85,139-142`. |
| Detalle de partido | `PageSkeleton` global | “Partido no encontrado” | No | Error de partido, error de prediction y error de red se agrupan; prediction puede degradar a ceros y H2H se omite: `app/partidos/[id]/page.tsx:1025-1051`; `lib/api.ts:794-804`. |
| Auth | No hay skeleton de formulario; botón se deshabilita | Alert por formulario | Reenvío manual | `login`, registro, recuperación y reset permiten reintentar manualmente: `app/cuenta/*/page.tsx`. |

`apiFetch` tiene timeout de 12 segundos, pero no reintenta: `apps/web/lib/api.ts:6-7,35-86`. Los `fetch` directos de auth y Wompi no comparten timeout: `apps/web/lib/auth.ts:68-143`; `apps/web/lib/wompi.ts:61-106`. No existe un error boundary de ruta (`error.tsx`) ni un loading boundary (`loading.tsx`) en el código fuente.

---

## 10. Tests y validaciones

### Tests de frontend

- No hay carpetas `test`, `tests`, `__tests__` ni `e2e` bajo `apps/web`.
- No hay archivos `*.test.*` o `*.spec.*` en `apps/web`.
- `apps/web/package.json:5-10` no tiene script `test`; `npm.cmd test` devuelve `Missing script: "test"`.
- La protección disponible es TypeScript y build, no una suite de tests de UI, integración HTTP o E2E.

### Comandos ejecutados

| Comando | Resultado observado |
|---|---|
| `npx.cmd tsc --noEmit --incremental false` | **Pasa**, sin salida de error. |
| `npm.cmd run build` | **Pasa**. Next 16.2.6 compila, ejecuta TypeScript, genera 13 páginas estáticas/dinámicas y muestra todas las rutas enumeradas. Emite warning porque `images.domains` está deprecated y recomienda `remotePatterns`: `apps/web/next.config.mjs:3-20`. |
| `npm.cmd run lint` | **Falla antes de analizar archivos**: `eslint` no se reconoce. `eslint` no aparece en `dependencies` ni `devDependencies`: `apps/web/package.json:26-33`. Tampoco se encontró configuración ESLint en `apps/web`. |
| `npm.cmd test` | **No disponible**: falta el script `test`. |
| `npx.cmd tsc --noEmit --incremental false --noUnusedLocals --noUnusedParameters` | **Falla** por 11 símbolos/imports sin uso: `MarketTable`, `EmptyCard`, dos parámetros `model`, `React` en `league-accordion`, dos helpers del generador, prop `matches`, parámetro `url` de `cdnutf` y tipos `TacticalFactor`/`MarketOdds`. Referencias: `app/partidos/[id]/page.tsx:40,140,371,788`; `components/betmind/league-accordion.tsx:3`; `ticket-generator.tsx:111,139,183`; `components/ui/team-logo.tsx:14`; `lib/api.ts:1`. |

No hay workflow CI que ejecute frontend; el workflow visible `.github/workflows/daily_predictions.yml:31-54` instala y ejecuta Python/backend batch, sin `npm`, `pnpm`, `tsc`, lint, build ni tests web.

---

## Resumen factual

El frontend vigente es una aplicación Next App Router con 12 rutas físicas, React 19, estado local distribuido y cliente HTTP propio. La sesión real se obtiene de `/users/me`; PRO usa `user.is_pro` con cache síncrono para gates no reactivos y un flag local para pruebas anónimas. Los datos de partidos, ligas, predicciones, tickets, bankroll y suscripciones vienen de la API; tickets anónimos, tema, onboarding, contador diario y cache/fallback de tracking usan `localStorage`.

No hay cache compartido ni deduplicación de requests. Home, cartelera y generador piden partidos de forma independiente; múltiples instancias de auth y bankroll repiten consultas dentro de una misma ruta. La vista de análisis es un archivo monolítico de 1.095 líneas con cuatro tabs y gates PRO client-side. Los estados de carga/error/retry existen en la mayoría de bloques, pero ligas, resumen de Home, generación de tickets y detalle tienen degradaciones silenciosas o sin retry.

La base de tokens de tema existe para claro y oscuro, pero el exportador Canvas, Sonner, `themeColor` y varios overlays mantienen decisiones oscuras fuera del sistema semántico. No hay tests frontend ni script de test. `tsc` y `next build` pasan; lint no es ejecutable por falta de ESLint.
