"use client";

import { useState, useEffect, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { get } from "@/lib/api";

/**
 * Search hook with debounced typeahead for company search.
 * Uses TanStack Query with a debounced query string (300ms debounce).
 * Only fetches when query >= 2 characters.
 *
 * Validates: Requirements 4.1, 4.2, 4.3, 4.4
 */

export interface SearchResult {
  id: string;
  name: string;
  client_status: "Client" | "Prospect" | "Unknown";
  industry: string | null;
  overall_score: number | null;
  similarity?: number;
}

export interface SearchResponse {
  results: SearchResult[];
  can_research: boolean;
  query: string;
}

function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(timer);
    };
  }, [value, delay]);

  return debouncedValue;
}

export function useSearch() {
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 300);

  const {
    data,
    isLoading,
    isFetching,
  } = useQuery<SearchResponse>({
    queryKey: ["companySearch", debouncedQuery],
    queryFn: () =>
      get<SearchResponse>(`/companies/search?q=${encodeURIComponent(debouncedQuery)}`),
    enabled: debouncedQuery.length >= 2,
    staleTime: 30 * 1000, // 30 seconds
  });

  const results = data?.results ?? [];
  const canResearch = data?.can_research ?? false;

  const clearSearch = useCallback(() => {
    setQuery("");
  }, []);

  return {
    query,
    setQuery,
    debouncedQuery,
    results,
    isLoading: isLoading && debouncedQuery.length >= 2,
    isFetching,
    canResearch,
    clearSearch,
  };
}
