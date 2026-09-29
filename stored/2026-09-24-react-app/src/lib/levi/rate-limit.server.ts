/**
 * In-memory per-key sliding-window rate limiter (server-only).
 *
 * Used to cap how often an authenticated caller can hit quota-spending server
 * functions (e.g. `leviComplete` -> xAI). The window slides: each key may make
 * up to `limit` calls per `windowMs`.
 *
 * FOLLOW-UP: this is per-process memory, so it does NOT work across multiple
 * server instances or restarts. Replace with a distributed limiter (Redis /
 * PGLite-backed token bucket) before relying on it for real quota protection.
 */

/** Result of a rate-limit check. */
export type RateLimitResult = { allowed: true } | { allowed: false; retryAfterMs: number };

const buckets = new Map<string, number[]>();

export function checkRateLimit(key: string, limit: number, windowMs: number): RateLimitResult {
  const now = Date.now();
  const recent = (buckets.get(key) ?? []).filter((t) => now - t < windowMs);
  if (recent.length >= limit) {
    const oldest = recent[0] ?? now;
    return { allowed: false, retryAfterMs: Math.max(0, windowMs - (now - oldest)) };
  }
  recent.push(now);
  buckets.set(key, recent);
  // Keep memory bounded: when many keys accumulate, sweep fully-expired buckets.
  if (buckets.size > 10_000) {
    for (const [k, stamps] of buckets) {
      if (stamps.every((t) => now - t >= windowMs)) buckets.delete(k);
    }
  }
  return { allowed: true };
}
