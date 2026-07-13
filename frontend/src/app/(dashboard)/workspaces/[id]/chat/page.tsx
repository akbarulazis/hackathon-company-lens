"use client";

import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { get, post, getAccessToken } from "@/lib/api";
import { WebSocketManager } from "@/lib/ws";

interface ChatMessage {
  id: number;
  workspace_id: number;
  user_id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

interface ChatHistoryResponse {
  messages: ChatMessage[];
}

interface ChatSubmitResponse {
  message_id: number;
  status: string;
}

export default function ChatPage({
  params,
}: {
  params: { id: string };
}) {
  const workspaceId = params.id;
  const queryClient = useQueryClient();

  const [input, setInput] = useState("");
  const [streamingContent, setStreamingContent] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocketManager | null>(null);

  // Fetch chat history on mount
  const { data: historyData, isLoading: isLoadingHistory } =
    useQuery<ChatHistoryResponse>({
      queryKey: ["chat-history", workspaceId],
      queryFn: () => get<ChatHistoryResponse>(`/workspaces/${workspaceId}/chat/history`),
    });

  // Sync history data to local state
  useEffect(() => {
    if (historyData?.messages) {
      setMessages(historyData.messages);
    }
  }, [historyData]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

  // WebSocket for streaming chat tokens
  useEffect(() => {
    const token = getAccessToken();
    if (!token) return;

    const ws = new WebSocketManager({
      token,
    });

    ws.on("chat.token", (data) => {
      if (String(data.workspace_id) !== workspaceId) return;

      if (data.done) {
        // Streaming complete — finalize the assistant message
        setIsStreaming(false);
        setStreamingContent((prev) => {
          const finalContent = prev + (data.token ?? "");
          // Add the completed assistant message to messages
          const assistantMessage: ChatMessage = {
            id: Date.now(), // Temporary ID until we refetch
            workspace_id: parseInt(workspaceId),
            user_id: 0,
            role: "assistant",
            content: finalContent,
            created_at: new Date().toISOString(),
          };
          setMessages((msgs) => [...msgs, assistantMessage]);
          return "";
        });
        // Invalidate history to get server-persisted messages
        queryClient.invalidateQueries({
          queryKey: ["chat-history", workspaceId],
        });
      } else {
        // Accumulate streaming tokens
        setStreamingContent((prev) => prev + (data.token ?? ""));
      }
    });

    ws.connect();
    wsRef.current = ws;

    return () => {
      ws.disconnect();
      wsRef.current = null;
    };
  }, [workspaceId, queryClient]);

  // Submit chat message mutation
  const sendMutation = useMutation({
    mutationFn: (message: string) =>
      post<ChatSubmitResponse>(`/workspaces/${workspaceId}/chat`, { message }),
    onMutate: (message) => {
      // Optimistically add user message to UI
      const userMessage: ChatMessage = {
        id: Date.now(),
        workspace_id: parseInt(workspaceId),
        user_id: 0,
        role: "user",
        content: message,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMessage]);
      setIsStreaming(true);
      setStreamingContent("");
    },
    onError: () => {
      setIsStreaming(false);
      setStreamingContent("");
    },
  });

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || isStreaming || sendMutation.isPending) return;
    setInput("");
    sendMutation.mutate(trimmed);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (isLoadingHistory) {
    return (
      <div className="container mx-auto p-6">
        <div className="flex items-center justify-center min-h-[200px]">
          <span className="loading loading-spinner loading-lg"></span>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 flex flex-col h-[calc(100vh-4rem)]">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Workspace Chat</h1>
        <span className="text-sm text-base-content/60">
          Ask questions about companies in this workspace
        </span>
      </div>

      {/* Message History */}
      <div className="flex-1 overflow-y-auto bg-base-200 rounded-lg p-4 space-y-4 min-h-0">
        {messages.length === 0 && !isStreaming && (
          <div className="flex items-center justify-center h-full text-base-content/50">
            <div className="text-center max-w-md">
              <p className="text-lg font-medium mb-2">Start a conversation</p>
              <p className="text-sm mb-6">
                Ask questions about companies in this workspace, or try one of these:
              </p>
              <div className="grid gap-2 text-left">
                {[
                  "Which company has the strongest financial position?",
                  "Compare the risk profiles of all companies",
                  "What banking products would fit each company?",
                  "Which company should we pursue first and why?",
                  "Summarize the key revenue opportunities across all companies",
                  "What are the main risks we should watch for?",
                ].map((q) => (
                  <button
                    key={q}
                    className="text-left px-4 py-2.5 rounded-lg border border-base-300 bg-base-100 text-sm text-base-content hover:border-primary/40 hover:bg-base-200 transition-colors"
                    onClick={() => {
                      setInput(q);
                      // Auto-submit
                      sendMutation.mutate(q);
                    }}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`chat ${msg.role === "user" ? "chat-end" : "chat-start"}`}
          >
            <div className="chat-header text-xs text-base-content/50 mb-1">
              {msg.role === "user" ? "You" : "Assistant"}
            </div>
            <div
              className={`chat-bubble ${
                msg.role === "user"
                  ? "chat-bubble-primary"
                  : "chat-bubble-neutral"
              }`}
            >
              <div className="whitespace-pre-wrap">{msg.content}</div>
            </div>
            <div className="chat-footer text-xs text-base-content/40 mt-1">
              {new Date(msg.created_at).toLocaleTimeString()}
            </div>
          </div>
        ))}

        {/* Streaming assistant response */}
        {isStreaming && (
          <div className="chat chat-start">
            <div className="chat-header text-xs text-base-content/50 mb-1">
              Assistant
            </div>
            <div className="chat-bubble chat-bubble-neutral">
              {streamingContent ? (
                <div className="whitespace-pre-wrap">{streamingContent}</div>
              ) : (
                <span className="loading loading-dots loading-sm"></span>
              )}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="mt-4 flex gap-2">
        <input
          type="text"
          className="input input-bordered flex-1"
          placeholder="Ask about companies in this workspace..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isStreaming || sendMutation.isPending}
        />
        <button
          className="btn btn-primary"
          onClick={handleSend}
          disabled={
            !input.trim() || isStreaming || sendMutation.isPending
          }
        >
          {sendMutation.isPending ? (
            <span className="loading loading-spinner loading-sm"></span>
          ) : (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
              className="w-5 h-5"
            >
              <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
            </svg>
          )}
        </button>
      </div>

      {/* Error display */}
      {sendMutation.isError && (
        <div className="alert alert-error mt-2">
          <span>
            {sendMutation.error instanceof Error
              ? sendMutation.error.message
              : "Failed to send message."}
          </span>
        </div>
      )}
    </div>
  );
}
