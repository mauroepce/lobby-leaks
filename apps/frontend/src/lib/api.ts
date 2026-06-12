/**
 * Thin fetch wrappers around the public LobbyLeaks API.
 *
 * Types are imported from the auto-generated TS SDK at
 * `clients/ts/models/`. We don't use the SDK's runtime (it ships a
 * heavy OpenAPI-generator base class); these helpers are ~30 lines
 * and let RSC do the caching for us.
 */

import type { SearchResponse } from "@sdk/models/SearchResponse";
import type { GraphResponse } from "@sdk/models/GraphResponse";

import { getApiBaseUrl, getDefaultTenant } from "./env";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function get<T>(path: string): Promise<T> {
  // `cache: "no-store"` because the underlying canonical store is
  // refreshed by the ingest pipeline; we don't want the Next data
  // cache to serve stale rows. Once we add explicit revalidation
  // hooks, this becomes `revalidate: 60` or similar.
  const res = await fetch(`${getApiBaseUrl()}${path}`, { cache: "no-store" });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, `API ${res.status} on ${path}: ${text.slice(0, 200)}`);
  }
  return (await res.json()) as T;
}

export async function searchEntities(
  query: string,
  options: { tenant?: string; limit?: number } = {},
): Promise<SearchResponse> {
  const params = new URLSearchParams({
    q: query,
    tenant: options.tenant ?? getDefaultTenant(),
    limit: String(options.limit ?? 20),
  });
  return get<SearchResponse>(`/api/v1/search?${params}`);
}

export async function fetchSubgraph(
  centerId: string,
  options: { tenant?: string; depth?: 1 | 2; limitEvents?: number } = {},
): Promise<GraphResponse> {
  const params = new URLSearchParams({
    center: centerId,
    tenant: options.tenant ?? getDefaultTenant(),
    depth: String(options.depth ?? 2),
    limit_events: String(options.limitEvents ?? 50),
  });
  return get<GraphResponse>(`/api/v1/graph?${params}`);
}

export { ApiError };
