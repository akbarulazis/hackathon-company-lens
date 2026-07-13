"use client";

import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { get, post } from "@/lib/api";
import ReactMarkdown from "react-markdown";

interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

interface ChatHistoryResponse {
  messages: ChatMessage[];
}

interface ChatResponse {
  response: string;
}

const TEMPLATE_QUESTIONS = [
  "Which company has the strongest financials?",
  "Compare risk profiles of all companies",
  "What banking products fit each company?",
  "Which company should we pursue first?",
  "Summarize revenue opportunities",
];

export default function ChatSidebar({ workspaceId }: { workspaceId: string }) {
  const queryClient = useQueryClient();
  const [input, setInput] = useState("");
  const [isWaiting, setIsWaiting] = useState(false);
  const [localMessages, setLocalMessages] = useState<ChatMessage[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Fetch history on mount
  const { data: historyData } = useQuery<ChatHistoryResponse>({
    queryKey: ["chat-history", workspaceId],
    queryFn: () => get<ChatHistoryResponse>(`/workspaces/${workspaceId}/chat/history`),
  });

  useEffect(() => {
    if (historyData?.messages) {
      setLocalMessages(historyData.messages);
    }
  }, [historyData]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [localMessages]);

  const sendMessage = async (text: string) => {
    if (!text.trim() || isWaiting) return;

    // Add user message
    const userMsg: ChatMessage = {
      id: Date.now(),
      role: "user",
      content: text.trim(),
      created_at: new Date().toISOString(),
    };
    setLocalMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsWaiting(true);

    try {
      const response = await post<ChatResponse>(`/workspaces/${workspaceId}/chat`, { message: text.trim() });

      // Add assistant message
      const assistantMsg: ChatMessage = {
        id: Date.now() + 1,
        role: "assistant",
        content: response.response,
        created_at: new Date().toISOString(),
      };
      setLocalMessages((prev) => [...prev, assistantMsg]);
    } catch {
      const errorMsg: ChatMessage = {
        id: Date.now() + 1,
        role: "assistant",
        content: "Sorry, I couldn't process that request. Please try again.",
        created_at: new Date().toISOString(),
      };
      setLocalMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsWaiting(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-base-300">
        <h3 className="text-[14px] font-medium">AI Assistant</h3>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {localMessages.length === 0 && !isWaiting && (
          <div className="space-y-2 pt-4">
            <p className="text-[12px] text-center" style={{ color: "#9c9fa5" }}>
              Ask about your companies
            </p>
            {TEMPLATE_QUESTIONS.map((q) => (
              <button
                key={q}
                onClick={() => sendMessage(q)}
                className="w-full text-left px-3 py-2 rounded-lg border border-base-300 text-[12px] hover:bg-base-200 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {localMessages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className="max-w-[85%] px-3 py-2 rounded-lg text-[13px] leading-relaxed"
              style={{
                backgroundColor: msg.role === "user" ? "#111111" : "#ffffff",
                color: msg.role === "user" ? "#ffffff" : "#111111",
                border: msg.role === "assistant" ? "1px solid #d3cec6" : "none",
              }}
            >
              {msg.role === "assistant" ? (
                <div className="prose prose-xs max-w-none [&_p]:m-0 [&_li]:m-0">
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                </div>
              ) : (
                <span>{msg.content}</span>
              )}
            </div>
          </div>
        ))}

        {isWaiting && (
          <div className="flex justify-start">
            <div className="px-3 py-2 rounded-lg bg-base-100 border border-base-300">
              <span className="inline-flex gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-base-content/40 animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="w-1.5 h-1.5 rounded-full bg-base-content/40 animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="w-1.5 h-1.5 rounded-full bg-base-content/40 animate-bounce" style={{ animationDelay: "300ms" }} />
              </span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-base-300">
        <div className="flex gap-2">
          <input
            type="text"
            className="flex-1 px-3 py-2 text-[13px] rounded-lg border border-base-300 bg-base-100 focus:outline-none focus:border-primary/40"
            placeholder="Ask a question..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage(input)}
            disabled={isWaiting}
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || isWaiting}
            className="px-3 py-2 rounded-lg bg-primary text-primary-content text-[12px] font-medium disabled:opacity-40"
          >
            →
          </button>
        </div>
      </div>
    </div>
  );
}
