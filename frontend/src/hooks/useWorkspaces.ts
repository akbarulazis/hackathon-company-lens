"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { get, post, put, del } from "@/lib/api";

// --- Types ---

export interface Workspace {
  id: number;
  name: string;
  company_limit: number;
  company_count: number;
  created_at: string;
  updated_at: string;
}

export interface CompanyInWorkspace {
  id: number;
  name: string;
  status: string;
  client_status: string;
  overall_score: number | null;
  industry: string | null;
}

export interface WorkspaceDetail extends Workspace {
  companies: CompanyInWorkspace[];
}

export interface ScoreDimensions {
  financial_health: number;
  business_risk: number;
  growth_potential: number;
  product_fit: number;
  relationship_accessibility: number;
}

export interface CompanyAnalytics {
  id: number;
  name: string;
  overall_score: number;
  financial_health: number | null;
  business_risk: number | null;
  growth_potential: number | null;
  product_fit: number | null;
  relationship_accessibility: number | null;
}

export interface ScoreHistoryPoint {
  scored_at: string;
  overall_score: number;
  financial_health: number;
  business_risk: number;
  growth_potential: number;
  product_fit: number;
  relationship_accessibility: number;
}

export interface WorkspaceAnalytics {
  companies: CompanyAnalytics[];
  score_history: Record<string, ScoreHistoryPoint[]>;
}

// --- Query Keys ---

export const workspaceKeys = {
  all: ["workspaces"] as const,
  detail: (id: number) => ["workspaces", id] as const,
  analytics: (id: number) => ["workspaces", id, "analytics"] as const,
};

// --- Queries ---

export function useWorkspaces() {
  return useQuery({
    queryKey: workspaceKeys.all,
    queryFn: () => get<Workspace[]>("/workspaces"),
  });
}

export function useWorkspaceDetail(id: number) {
  return useQuery({
    queryKey: workspaceKeys.detail(id),
    queryFn: () => get<WorkspaceDetail>(`/workspaces/${id}`),
    enabled: !!id,
  });
}

export function useWorkspaceAnalytics(id: number) {
  return useQuery({
    queryKey: workspaceKeys.analytics(id),
    queryFn: () => get<WorkspaceAnalytics>(`/workspaces/${id}/analytics`),
    enabled: !!id,
  });
}

// --- Mutations ---

export function useCreateWorkspace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => post<Workspace>("/workspaces", { name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: workspaceKeys.all });
    },
  });
}

export function useUpdateWorkspace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) =>
      put<Workspace>(`/workspaces/${id}`, { name }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: workspaceKeys.all });
      queryClient.invalidateQueries({ queryKey: workspaceKeys.detail(variables.id) });
    },
  });
}

export function useDeleteWorkspace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => del(`/workspaces/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: workspaceKeys.all });
    },
  });
}

export function useAddCompanyToWorkspace(workspaceId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (companyId: number) =>
      post(`/workspaces/${workspaceId}/companies`, { company_id: companyId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: workspaceKeys.detail(workspaceId) });
      queryClient.invalidateQueries({ queryKey: workspaceKeys.analytics(workspaceId) });
      queryClient.invalidateQueries({ queryKey: workspaceKeys.all });
    },
  });
}

export function useRemoveCompanyFromWorkspace(workspaceId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (companyId: number) =>
      del(`/workspaces/${workspaceId}/companies/${companyId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: workspaceKeys.detail(workspaceId) });
      queryClient.invalidateQueries({ queryKey: workspaceKeys.analytics(workspaceId) });
      queryClient.invalidateQueries({ queryKey: workspaceKeys.all });
    },
  });
}
