"use client";

import { QueryClient } from "@tanstack/react-query";

/**
 * Singleton QueryClient. We default to conservative stale times so that
 * polling-driven hooks (alerts, config) can opt into shorter intervals
 * via the per-query `staleTime` override.
 */
let _client: QueryClient | null = null;

export function getQueryClient(): QueryClient {
  if (_client) {
    return _client;
  }
  _client = new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        gcTime: 5 * 60_000,
        retry: 1,
        refetchOnWindowFocus: false,
      },
      mutations: {
        retry: 0,
      },
    },
  });
  return _client;
}
