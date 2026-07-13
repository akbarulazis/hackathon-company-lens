"use client";

import { useState } from "react";
import Link from "next/link";
import {
  useWorkspaces,
  useCreateWorkspace,
  useDeleteWorkspace,
} from "@/hooks/useWorkspaces";

export default function WorkspacesPage() {
  const { data: workspaces, isLoading, error } = useWorkspaces();
  const createMutation = useCreateWorkspace();
  const deleteMutation = useDeleteWorkspace();

  const [newName, setNewName] = useState("");
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; name: string } | null>(null);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    await createMutation.mutateAsync(newName.trim());
    setNewName("");
    setShowCreateForm(false);
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    await deleteMutation.mutateAsync(deleteTarget.id);
    setDeleteTarget(null);
  };

  if (isLoading) {
    return (
      <div className="p-8 flex justify-center">
        <span className="loading loading-spinner loading-lg text-primary"></span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-error/10 border border-error/20 rounded-lg p-4 text-error text-sm">
          Failed to load workspaces. Please try again.
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-medium text-base-content" style={{ letterSpacing: "-0.5px" }}>
          Workspaces
        </h1>
        <button
          className="btn btn-sm bg-primary text-primary-content border-none hover:bg-black rounded-lg"
          onClick={() => setShowCreateForm(true)}
        >
          + New workspace
        </button>
      </div>

      {/* Create Form Modal */}
      {showCreateForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-base-100 rounded-xl border border-base-300 p-6 w-full max-w-md shadow-xl">
            <h2 className="text-lg font-medium mb-4">Create Workspace</h2>
            <form onSubmit={handleCreate}>
              <input
                type="text"
                className="input input-bordered w-full mb-4"
                placeholder="Workspace name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                maxLength={100}
                autoFocus
              />
              {createMutation.error && (
                <p className="text-error text-sm mb-3">{createMutation.error.message}</p>
              )}
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  className="btn btn-sm btn-ghost"
                  onClick={() => { setShowCreateForm(false); setNewName(""); }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-sm bg-primary text-primary-content border-none hover:bg-black rounded-lg"
                  disabled={!newName.trim() || createMutation.isPending}
                >
                  {createMutation.isPending ? "Creating..." : "Create"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-base-100 rounded-xl border border-base-300 p-6 w-full max-w-sm shadow-xl">
            <h2 className="text-lg font-medium mb-2">Delete workspace</h2>
            <p className="text-sm text-secondary mb-5">
              Are you sure you want to delete <strong>{deleteTarget.name}</strong>? All data including chat history and comparison reports will be permanently removed.
            </p>
            <div className="flex justify-end gap-2">
              <button className="btn btn-sm btn-ghost" onClick={() => setDeleteTarget(null)}>Cancel</button>
              <button
                className="btn btn-sm bg-error text-white border-none hover:bg-red-700 rounded-lg"
                onClick={handleDelete}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Workspace List */}
      {workspaces && workspaces.length === 0 ? (
        <div className="bg-base-100 rounded-xl border border-base-300 p-12 text-center">
          <p className="text-secondary text-sm mb-4">No workspaces yet.</p>
          <button
            className="btn btn-sm bg-primary text-primary-content border-none hover:bg-black rounded-lg"
            onClick={() => setShowCreateForm(true)}
          >
            Create your first workspace
          </button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {workspaces?.map((ws) => (
            <div
              key={ws.id}
              className="bg-base-100 rounded-xl border border-base-300 p-5 hover:border-primary/30 transition-colors"
            >
              <Link href={`/workspaces/${ws.id}`} className="block mb-3">
                <h3 className="text-base font-medium text-base-content hover:underline">
                  {ws.name}
                </h3>
              </Link>
              <div className="flex items-center justify-between">
                <span className="text-xs text-secondary">
                  {ws.company_count}/{ws.company_limit} companies
                </span>
                <button
                  className="text-xs text-error/70 hover:text-error"
                  onClick={() => setDeleteTarget({ id: ws.id, name: ws.name })}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
