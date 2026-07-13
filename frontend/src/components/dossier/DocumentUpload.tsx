"use client";

/**
 * Document Upload component for company dossier.
 * Allows uploading PDF documents (max 20MB) and displays document list
 * with real-time status updates via WebSocket.
 *
 * Validates: Requirements 12.1, 12.6, 12.8
 */

import { useState, useRef, useCallback, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { get, getAccessToken, API_BASE } from "@/lib/api";
import { useWebSocket, WebSocketEventByType } from "@/hooks/useWebSocket";

// ─── Types ─────────────────────────────────────────────────────────────────────

interface CompanyDocument {
  id: number;
  filename: string;
  status: "pending" | "processing" | "ready" | "failed";
  page_count: number | null;
  chunk_count: number | null;
  key_points: string | null;
  created_at: string;
}

interface DocumentUploadProps {
  companyId: number;
}

// ─── Constants ─────────────────────────────────────────────────────────────────

const MAX_FILE_SIZE_MB = 20;
const MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024;

// ─── Status Badge Component ────────────────────────────────────────────────────

function StatusBadge({ status }: { status: CompanyDocument["status"] }) {
  const config: Record<CompanyDocument["status"], { class: string; label: string }> = {
    pending: { class: "badge-warning", label: "Pending" },
    processing: { class: "badge-info", label: "Processing" },
    ready: { class: "badge-success", label: "Ready" },
    failed: { class: "badge-error", label: "Failed" },
  };

  const { class: badgeClass, label } = config[status] ?? config.pending;

  return <span className={`badge badge-sm ${badgeClass}`}>{label}</span>;
}

// ─── Document List Item ────────────────────────────────────────────────────────

function DocumentListItem({ doc }: { doc: CompanyDocument }) {
  const createdDate = new Date(doc.created_at).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <tr>
      <td className="font-medium">
        <div className="flex items-center gap-2">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-4 w-4 text-error shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
            />
          </svg>
          <span className="truncate max-w-[200px]" title={doc.filename}>
            {doc.filename}
          </span>
        </div>
      </td>
      <td>
        <StatusBadge status={doc.status} />
      </td>
      <td className="text-sm text-base-content/70">
        {doc.page_count !== null ? `${doc.page_count} pages` : "—"}
      </td>
      <td className="text-sm text-base-content/70">{createdDate}</td>
    </tr>
  );
}

// ─── Main Component ────────────────────────────────────────────────────────────

export default function DocumentUpload({ companyId }: DocumentUploadProps) {
  const queryClient = useQueryClient();
  const { subscribe, unsubscribe } = useWebSocket();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  // ─── Fetch document list ───────────────────────────────────────────────────

  const {
    data: documents,
    isLoading: isLoadingDocs,
  } = useQuery<CompanyDocument[]>({
    queryKey: ["company-documents", companyId],
    queryFn: async () => {
      const data = await get<{ documents: CompanyDocument[] }>(`/companies/${companyId}/documents`);
      return data.documents ?? [];
    },
    enabled: !!companyId,
  });

  // ─── WebSocket subscription for real-time status updates ───────────────────

  useEffect(() => {
    const handleDocumentStatus = (event: WebSocketEventByType<"document.status">) => {
      if (event.company_id !== companyId) return;

      // Invalidate the document list query to refetch with updated status
      queryClient.invalidateQueries({
        queryKey: ["company-documents", companyId],
      });
    };

    subscribe("document.status", handleDocumentStatus);

    return () => {
      unsubscribe("document.status", handleDocumentStatus);
    };
  }, [companyId, subscribe, unsubscribe, queryClient]);

  // ─── File selection handler ────────────────────────────────────────────────

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setUploadError(null);
      const file = e.target.files?.[0] ?? null;

      if (!file) {
        setSelectedFile(null);
        return;
      }

      // Validate file type
      if (file.type !== "application/pdf") {
        setUploadError("Only PDF files are accepted.");
        setSelectedFile(null);
        if (fileInputRef.current) fileInputRef.current.value = "";
        return;
      }

      // Validate file size
      if (file.size > MAX_FILE_SIZE_BYTES) {
        setUploadError(`File size exceeds ${MAX_FILE_SIZE_MB}MB limit.`);
        setSelectedFile(null);
        if (fileInputRef.current) fileInputRef.current.value = "";
        return;
      }

      setSelectedFile(file);
    },
    []
  );

  // ─── Upload handler ────────────────────────────────────────────────────────

  const handleUpload = useCallback(async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    setUploadError(null);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const token = getAccessToken();
      const response = await fetch(
        `${API_BASE}/companies/${companyId}/documents`,
        {
          method: "POST",
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: formData,
        }
      );

      if (!response.ok) {
        const errorBody = await response.json().catch(() => ({}));
        throw new Error(
          errorBody.detail ?? `Upload failed with status ${response.status}`
        );
      }

      // Clear file input and refetch document list
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      queryClient.invalidateQueries({
        queryKey: ["company-documents", companyId],
      });
    } catch (err) {
      setUploadError(
        err instanceof Error ? err.message : "Upload failed. Please try again."
      );
    } finally {
      setIsUploading(false);
    }
  }, [selectedFile, companyId, queryClient]);

  // ─── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Upload Section */}
      <div className="card bg-base-200">
        <div className="card-body">
          <h3 className="card-title text-base">Upload Document</h3>
          <p className="text-sm text-base-content/60">
            Upload PDF documents (max {MAX_FILE_SIZE_MB}MB) to enrich the company knowledge base.
          </p>

          <div className="flex flex-col sm:flex-row gap-3 mt-2">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf"
              onChange={handleFileChange}
              disabled={isUploading}
              className="file-input file-input-bordered file-input-sm w-full sm:w-auto flex-1"
              aria-label="Select PDF file"
            />
            <button
              className="btn btn-primary btn-sm"
              onClick={handleUpload}
              disabled={!selectedFile || isUploading}
            >
              {isUploading ? (
                <>
                  <span className="loading loading-spinner loading-xs" />
                  Uploading...
                </>
              ) : (
                <>
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    className="h-4 w-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    aria-hidden="true"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
                    />
                  </svg>
                  Upload
                </>
              )}
            </button>
          </div>

          {/* Upload Error */}
          {uploadError && (
            <div className="alert alert-error alert-sm mt-2">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-4 w-4 shrink-0"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z"
                />
              </svg>
              <span className="text-sm">{uploadError}</span>
            </div>
          )}
        </div>
      </div>

      {/* Document List Section */}
      <div className="card bg-base-200">
        <div className="card-body">
          <h3 className="card-title text-base">Documents</h3>

          {isLoadingDocs ? (
            <div className="flex justify-center py-6">
              <span className="loading loading-spinner loading-md" />
            </div>
          ) : !documents || documents.length === 0 ? (
            <p className="text-sm text-base-content/60 py-4 text-center">
              No documents uploaded yet. Upload a PDF to get started.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="table table-sm" aria-label="Company documents">
                <thead>
                  <tr>
                    <th>Filename</th>
                    <th>Status</th>
                    <th>Pages</th>
                    <th>Uploaded</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((doc) => (
                    <DocumentListItem key={doc.id} doc={doc} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
