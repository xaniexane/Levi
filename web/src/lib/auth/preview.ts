/**
 * Shared LIVE-PREVIEW OAuth client (server-only — NEVER import from the client).
 *
 * The sandbox serves each live preview on a dynamic `https://*.grok-sandbox.com`
 * URL, which can't be pre-registered per app. The broker instead exposes ONE
 * shared "preview" client that accepts any
 * `https://*.grok-sandbox.com/api/auth/oauth2/callback/*`
 * (broker: `app-builder-deployer/auth/src/preview-oauth.ts`). The sandbox (or
 * whoever runs it) injects the matching `GROK_PREVIEW_CLIENT_SECRET` into the
 * environment — no platform injection, no demo/mock users. When deployed the
 * deployer injects a per-app `GROK_AUTH_*` that overrides these (see `server.ts`).
 *
 * These MUST equal the broker's `GROK_PREVIEW_CLIENT_ID` /
 * `GROK_PREVIEW_CLIENT_SECRET` (set in the broker's environment; the broker
 * stores only the secret's `base64url(SHA-256)` hash). This is a dedicated,
 * low-privilege client (preview-only, `*.grok-sandbox.com`) — rotate it by
 * regenerating the broker env var and the injected secret together.
 *
 * SECURITY: no secret is ever committed to this file. A previous revision baked
 * a real client secret into source — that value is compromised (it lived in git
 * history) and MUST be rotated in the broker's environment. An unset
 * `GROK_PREVIEW_CLIENT_SECRET` leaves the constant empty, which disables
 * federated sign-in fail-closed via `authConfigured` in `./server.ts`.
 */
export const PREVIEW_CLIENT_ID = "grok_preview";
/** Injected secret — never committed. Empty disables federated sign-in (fail-closed). */
export const PREVIEW_CLIENT_SECRET =
  process.env.GROK_PREVIEW_CLIENT_SECRET?.trim() || "";

/** The shared auth broker issuer (OIDC discovery lives under it). */
export const GROK_ISSUER_DEFAULT = "https://auth.grok.me";

/**
 * Host patterns whose callbacks the preview client accepts. Better Auth derives
 * the live preview's real origin from the request host and validates it against
 * this list (wildcard-matched), so the OAuth `redirect_uri` becomes the concrete
 * `https://<preview-host>/api/auth/oauth2/callback/...` the broker allows.
 */
export const PREVIEW_ALLOWED_HOSTS = ["*.grok-sandbox.com"] as const;
