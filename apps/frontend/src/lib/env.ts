/**
 * Public env vars accessed lazily.
 *
 * Reading `process.env.NEXT_PUBLIC_*` at module load throws during
 * `next build`'s page-data collection step when the var isn't set (e.g.
 * in CI), so we defer the look-up to first use and throw only when a
 * request actually tries to hit the API without the URL configured.
 */

export function getApiBaseUrl(): string {
  const v = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!v) {
    throw new Error(
      "NEXT_PUBLIC_API_BASE_URL is not set — copy apps/frontend/.env.example to .env and fill it in.",
    );
  }
  return v.replace(/\/+$/, "");
}

export function getDefaultTenant(): string {
  return (process.env.NEXT_PUBLIC_DEFAULT_TENANT ?? "CL").toUpperCase();
}
