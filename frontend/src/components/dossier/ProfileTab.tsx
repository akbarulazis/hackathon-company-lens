"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ProfileTabProps {
  acquisitionBrief: string | null;
}

export default function ProfileTab({ acquisitionBrief }: ProfileTabProps) {
  if (!acquisitionBrief) {
    return (
      <div className="p-6 text-center">
        <p className="text-[15px]" style={{ color: "#626260" }}>
          No acquisition brief available yet.
        </p>
      </div>
    );
  }

  return (
    <div className="p-6">
      <article className="prose prose-sm md:prose-base max-w-none prose-headings:text-base-content prose-p:text-base-content/80 prose-a:text-primary prose-strong:text-base-content prose-table:text-sm">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {acquisitionBrief}
        </ReactMarkdown>
      </article>
    </div>
  );
}
