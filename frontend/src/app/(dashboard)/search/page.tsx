"use client";

import { GlobalSearch } from "@/components/GlobalSearch";

export default function SearchPage() {
  return (
    <div className="p-6 md:p-8">
      <h1
        className="text-2xl font-medium text-base-content mb-6"
        style={{ letterSpacing: "-0.5px" }}
      >
        Search Companies
      </h1>
      <div className="max-w-lg">
        <GlobalSearch />
      </div>
      <p className="text-sm text-secondary mt-4">
        Type at least 2 characters to search. If a company isn&apos;t found, you can research it with AI.
      </p>
    </div>
  );
}
