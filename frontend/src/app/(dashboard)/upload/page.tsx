"use client";

import { useState, useRef } from "react";
import { getAccessToken, API_BASE } from "@/lib/api";

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState<{ matched: number; unmatched: number; total: number; errors: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleUpload = async () => {
    if (!file) return;
    setIsUploading(true);
    setError(null);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const token = getAccessToken();
      const response = await fetch(`${API_BASE}/portfolio/import`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || `Upload failed: ${response.status}`);
      }

      const data = await response.json();
      setResult(data);
      setFile(null);
      if (fileRef.current) fileRef.current.value = "";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="p-6 md:p-8 max-w-2xl">
      <h1 className="text-2xl font-medium mb-2" style={{ letterSpacing: "-0.5px" }}>
        Portfolio Import
      </h1>
      <p className="text-sm mb-8" style={{ color: "#626260" }}>
        Upload your monthly bank portfolio extract (CSV or TSV). This page is for admin use.
      </p>

      {/* Upload Card */}
      <div className="bg-base-100 rounded-xl border border-base-300 p-6 space-y-4">
        <div>
          <label className="block text-[14px] font-medium mb-2">Select file</label>
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.tsv,.xlsx,.xls"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="file-input file-input-bordered w-full"
          />
          <p className="text-[12px] mt-1" style={{ color: "#9c9fa5" }}>
            Accepted: .csv, .tsv, .xlsx, .xls — with column convention (division_product_subproduct_metric)
          </p>
        </div>

        <button
          onClick={handleUpload}
          disabled={!file || isUploading}
          className="btn btn-sm bg-primary text-primary-content border-none hover:bg-black rounded-lg"
        >
          {isUploading ? "Importing..." : "Import Portfolio"}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="mt-4 p-4 rounded-lg" style={{ backgroundColor: "#fef2f2", border: "1px solid #fecaca" }}>
          <p className="text-[14px]" style={{ color: "#b91c1c" }}>{error}</p>
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="mt-4 p-4 rounded-lg" style={{ backgroundColor: "#f0fdf4", border: "1px solid #bbf7d0" }}>
          <p className="text-[14px] font-medium" style={{ color: "#166534" }}>Import Complete</p>
          <div className="mt-2 text-[13px] space-y-1" style={{ color: "#15803d" }}>
            <p>✓ Total rows: {result.total}</p>
            <p>✓ Matched to companies: {result.matched}</p>
            <p>○ Queued for review: {result.unmatched}</p>
            {result.errors.length > 0 && (
              <div className="mt-2">
                <p className="font-medium text-amber-700">Warnings:</p>
                {result.errors.map((e, i) => <p key={i} className="text-amber-600">• {e}</p>)}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
