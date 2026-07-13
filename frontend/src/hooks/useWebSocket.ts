"use client";

/**
 * React hook for WebSocket real-time event handling.
 * Connects on mount when authenticated, disconnects on unmount.
 * Dispatches typed events and shows DaisyUI toast notifications.
 *
 * Requirements: 6.1, 6.3, 6.4, 6.5, 15.4
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { getAccessToken } from "@/lib/api";
import {
  WebSocketManager,
  ConnectionStatus,
  WebSocketEvent,
  WebSocketEventType,
  WebSocketEventByType,
  TypedEventHandler,
} from "@/lib/ws";
import { addToast } from "@/components/ToastContainer";

// ─── Hook Return Type ──────────────────────────────────────────────────────────

export interface UseWebSocketReturn {
  /** Whether the WebSocket is currently connected */
  isConnected: boolean;
  /** Current connection status */
  status: ConnectionStatus;
  /** The last event received from the WebSocket */
  lastEvent: WebSocketEvent | null;
  /** Subscribe to a specific event type */
  subscribe: <T extends WebSocketEventType>(type: T, handler: TypedEventHandler<T>) => void;
  /** Unsubscribe from a specific event type */
  unsubscribe: <T extends WebSocketEventType>(type: T, handler: TypedEventHandler<T>) => void;
}

// ─── Toast notification helpers ────────────────────────────────────────────────

function handleResearchStatusToast(event: WebSocketEventByType<"research.status">): void {
  const { status, message } = event;
  switch (status) {
    case "ready":
      addToast("success", message || "Research completed successfully");
      break;
    case "failed":
      addToast("error", message || "Research pipeline failed");
      break;
    case "researching":
    case "profiling":
    case "scoring":
      addToast("info", message || `Research in progress: ${status}`);
      break;
  }
}

function handleDocumentStatusToast(event: WebSocketEventByType<"document.status">): void {
  const { status, message } = event;
  switch (status) {
    case "ready":
      addToast("success", message || "Document processing completed");
      break;
    case "failed":
      addToast("error", message || "Document processing failed");
      break;
    case "processing":
      addToast("info", message || "Document is being processed");
      break;
  }
}

function handleGenericToast(event: WebSocketEventByType<"toast">): void {
  addToast(event.level, event.message);
}

// ─── useWebSocket Hook ─────────────────────────────────────────────────────────

export function useWebSocket(): UseWebSocketReturn {
  const { isAuthenticated } = useAuth();
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [lastEvent, setLastEvent] = useState<WebSocketEvent | null>(null);
  const managerRef = useRef<WebSocketManager | null>(null);

  // Handle reconnection — query REST fallback for missed events
  const handleReconnect = useCallback(() => {
    // Optional: Query REST fallback endpoint for missed events during disconnection.
    // Example: apiFetch("/companies/research/status") to get current in-progress research status.
    // This is left as a hook point — consumers can subscribe to the "reconnect" behavior
    // via the status change from "reconnecting" → "connected".
  }, []);

  // Connect/disconnect based on auth state
  useEffect(() => {
    if (!isAuthenticated) {
      // Disconnect if user logs out
      if (managerRef.current) {
        managerRef.current.disconnect();
        managerRef.current = null;
      }
      setStatus("disconnected");
      return;
    }

    const token = getAccessToken();
    if (!token) return;

    // Create new manager if one doesn't exist
    if (!managerRef.current) {
      const manager = new WebSocketManager({
        token,
        onStatusChange: (newStatus) => {
          setStatus(newStatus);
        },
        onReconnect: handleReconnect,
      });

      // Register internal event handlers for toast notifications
      manager.on("research.status", (event) => {
        setLastEvent(event);
        handleResearchStatusToast(event);
      });

      manager.on("document.status", (event) => {
        setLastEvent(event);
        handleDocumentStatusToast(event);
      });

      manager.on("toast", (event) => {
        setLastEvent(event);
        handleGenericToast(event);
      });

      manager.on("comparison.status", (event) => {
        setLastEvent(event);
      });

      manager.on("comparison.result", (event) => {
        setLastEvent(event);
      });

      manager.on("chat.token", (event) => {
        setLastEvent(event);
      });

      managerRef.current = manager;
      manager.connect();
    } else {
      // Update token if manager already exists (e.g., token refreshed)
      managerRef.current.updateToken(token);
    }

    // Cleanup on unmount
    return () => {
      if (managerRef.current) {
        managerRef.current.disconnect();
        managerRef.current = null;
      }
    };
  }, [isAuthenticated, handleReconnect]);

  // Subscribe to a specific event type
  const subscribe = useCallback(
    <T extends WebSocketEventType>(type: T, handler: TypedEventHandler<T>) => {
      managerRef.current?.on(type, handler);
    },
    []
  );

  // Unsubscribe from a specific event type
  const unsubscribe = useCallback(
    <T extends WebSocketEventType>(type: T, handler: TypedEventHandler<T>) => {
      managerRef.current?.off(type, handler);
    },
    []
  );

  return {
    isConnected: status === "connected",
    status,
    lastEvent,
    subscribe,
    unsubscribe,
  };
}

// Re-export event types for consumer convenience
export type { WebSocketEvent, WebSocketEventType, WebSocketEventByType, TypedEventHandler };
