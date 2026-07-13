"use client";

/**
 * WebSocket connection manager with exponential backoff reconnection.
 * Provides authenticated per-user real-time event channel with typed events.
 *
 * Reconnection strategy:
 * - Start at 1 second delay
 * - Double on each attempt (1s, 2s, 4s, 8s, 16s, 30s, 30s...)
 * - Cap at 30 seconds max interval
 * - Max 10 reconnection attempts
 * - Reset attempt counter on successful connection
 */

// ─── Event Types ───────────────────────────────────────────────────────────────

export type WebSocketEvent =
  | { type: "research.status"; company_id: number; status: string; message: string; timestamp: string }
  | { type: "comparison.status"; workspace_id: number; report_id: number; status: string }
  | { type: "comparison.result"; workspace_id: number; report_id: number }
  | { type: "document.status"; document_id: number; company_id: number; status: string; message?: string }
  | { type: "chat.token"; workspace_id: number; token: string; done: boolean }
  | { type: "toast"; level: "info" | "success" | "warning" | "error"; message: string };

export type WebSocketEventType = WebSocketEvent["type"];

export type WebSocketEventByType<T extends WebSocketEventType> = Extract<WebSocketEvent, { type: T }>;

// ─── Connection Status ─────────────────────────────────────────────────────────

export type ConnectionStatus = "connecting" | "connected" | "disconnected" | "reconnecting" | "failed";

// ─── Event Handler Types ───────────────────────────────────────────────────────

export type TypedEventHandler<T extends WebSocketEventType> = (event: WebSocketEventByType<T>) => void;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type EventListenerMap = Map<WebSocketEventType, Set<TypedEventHandler<any>>>;

export type StatusChangeHandler = (status: ConnectionStatus) => void;
export type ReconnectHandler = () => void;

// ─── Options ───────────────────────────────────────────────────────────────────

export interface WebSocketManagerOptions {
  /** JWT token for authentication */
  token: string;
  /** Status change handler */
  onStatusChange?: StatusChangeHandler;
  /** Called when reconnection succeeds (for REST fallback queries) */
  onReconnect?: ReconnectHandler;
  /** Base URL for WebSocket connection (defaults to ws://localhost:8000) */
  baseUrl?: string;
}

// ─── Constants ─────────────────────────────────────────────────────────────────

const DEFAULT_WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";
const INITIAL_RECONNECT_DELAY = 1000; // 1 second
const MAX_RECONNECT_DELAY = 30000; // 30 seconds
const MAX_RECONNECT_ATTEMPTS = 10;

// ─── WebSocketManager Class ────────────────────────────────────────────────────

export class WebSocketManager {
  private ws: WebSocket | null = null;
  private token: string;
  private onStatusChange?: StatusChangeHandler;
  private onReconnect?: ReconnectHandler;
  private baseUrl: string;
  private reconnectAttempts = 0;
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  private status: ConnectionStatus = "disconnected";
  private intentionalClose = false;
  private wasConnected = false;
  private listeners: EventListenerMap = new Map();

  constructor(options: WebSocketManagerOptions) {
    this.token = options.token;
    this.onStatusChange = options.onStatusChange;
    this.onReconnect = options.onReconnect;
    this.baseUrl = options.baseUrl ?? DEFAULT_WS_URL;
  }

  /** Establish WebSocket connection */
  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    this.intentionalClose = false;
    this.setStatus("connecting");

    const url = `${this.baseUrl}/api/ws?token=${encodeURIComponent(this.token)}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      const isReconnection = this.wasConnected;
      this.reconnectAttempts = 0;
      this.wasConnected = true;
      this.setStatus("connected");

      // Notify about reconnection for REST fallback
      if (isReconnection && this.onReconnect) {
        this.onReconnect();
      }
    };

    this.ws.onmessage = (event: MessageEvent) => {
      this.handleMessage(event);
    };

    this.ws.onclose = (event) => {
      this.ws = null;

      if (this.intentionalClose) {
        this.setStatus("disconnected");
        return;
      }

      // Auth failure — don't reconnect
      if (event.code === 4001 || event.code === 4003) {
        this.setStatus("failed");
        return;
      }

      this.attemptReconnect();
    };

    this.ws.onerror = () => {
      // Error handling is done via onclose
    };
  }

  /** Disconnect WebSocket intentionally */
  disconnect(): void {
    this.intentionalClose = true;
    this.clearReconnectTimeout();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.setStatus("disconnected");
    this.wasConnected = false;
  }

  /** Update the authentication token (e.g., after refresh) */
  updateToken(token: string): void {
    this.token = token;
    // Reconnect with new token if currently connected
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.intentionalClose = true;
      this.ws.close();
      this.ws = null;
      this.intentionalClose = false;
      this.connect();
    }
  }

  /** Get current connection status */
  getStatus(): ConnectionStatus {
    return this.status;
  }

  /** Subscribe to a typed WebSocket event */
  on<T extends WebSocketEventType>(type: T, handler: TypedEventHandler<T>): void {
    if (!this.listeners.has(type)) {
      this.listeners.set(type, new Set());
    }
    this.listeners.get(type)!.add(handler);
  }

  /** Unsubscribe from a typed WebSocket event */
  off<T extends WebSocketEventType>(type: T, handler: TypedEventHandler<T>): void {
    const handlers = this.listeners.get(type);
    if (handlers) {
      handlers.delete(handler);
    }
  }

  /** Get current reconnect attempt count (useful for testing) */
  getReconnectAttempts(): number {
    return this.reconnectAttempts;
  }

  // ─── Private Methods ───────────────────────────────────────────────────────

  private handleMessage(event: MessageEvent): void {
    try {
      const data = JSON.parse(event.data) as WebSocketEvent;
      if (!data.type) return;

      const handlers = this.listeners.get(data.type);
      if (handlers) {
        handlers.forEach((handler) => {
          handler(data);
        });
      }
    } catch {
      // Silently ignore malformed messages
    }
  }

  private attemptReconnect(): void {
    if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      this.setStatus("failed");
      return;
    }

    this.setStatus("reconnecting");
    const delay = Math.min(
      INITIAL_RECONNECT_DELAY * Math.pow(2, this.reconnectAttempts),
      MAX_RECONNECT_DELAY
    );
    this.reconnectAttempts++;

    this.reconnectTimeout = setTimeout(() => {
      this.connect();
    }, delay);
  }

  private clearReconnectTimeout(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
  }

  private setStatus(status: ConnectionStatus): void {
    this.status = status;
    this.onStatusChange?.(status);
  }
}
