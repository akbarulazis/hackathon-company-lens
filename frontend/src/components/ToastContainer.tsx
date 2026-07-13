"use client";

import { useCallback, useEffect, useState } from "react";

// ─── Toast Types ───────────────────────────────────────────────────────────────

export type ToastLevel = "info" | "success" | "warning" | "error";

export interface Toast {
  id: string;
  level: ToastLevel;
  message: string;
  createdAt: number;
}

// ─── Toast Store (module-level singleton) ──────────────────────────────────────

type ToastListener = (toasts: Toast[]) => void;

let toasts: Toast[] = [];
const listeners = new Set<ToastListener>();
let nextId = 0;

const TOAST_DURATION = 5000; // 5 seconds auto-dismiss

function notifyListeners() {
  listeners.forEach((listener) => listener([...toasts]));
}

/** Add a toast notification. Can be called from anywhere. */
export function addToast(level: ToastLevel, message: string): void {
  const id = `toast-${++nextId}-${Date.now()}`;
  const toast: Toast = { id, level, message, createdAt: Date.now() };
  toasts = [...toasts, toast];
  notifyListeners();

  // Auto-dismiss after duration
  setTimeout(() => {
    removeToast(id);
  }, TOAST_DURATION);
}

/** Remove a specific toast by ID */
export function removeToast(id: string): void {
  toasts = toasts.filter((t) => t.id !== id);
  notifyListeners();
}

// ─── Alert class mapping for DaisyUI ──────────────────────────────────────────

const ALERT_CLASSES: Record<ToastLevel, string> = {
  info: "alert-info",
  success: "alert-success",
  warning: "alert-warning",
  error: "alert-error",
};

const ALERT_ICONS: Record<ToastLevel, string> = {
  info: "ℹ️",
  success: "✓",
  warning: "⚠️",
  error: "✕",
};

// ─── ToastContainer Component ──────────────────────────────────────────────────

/**
 * Renders DaisyUI toast notifications in the bottom-right corner.
 * Place this component once at the root layout level.
 */
export function ToastContainer() {
  const [currentToasts, setCurrentToasts] = useState<Toast[]>([]);

  useEffect(() => {
    // Subscribe to toast updates
    const listener: ToastListener = (updatedToasts) => {
      setCurrentToasts(updatedToasts);
    };
    listeners.add(listener);

    // Initialize with current toasts
    setCurrentToasts([...toasts]);

    return () => {
      listeners.delete(listener);
    };
  }, []);

  const handleDismiss = useCallback((id: string) => {
    removeToast(id);
  }, []);

  if (currentToasts.length === 0) return null;

  return (
    <div className="toast toast-end toast-bottom z-50">
      {currentToasts.map((toast) => (
        <div
          key={toast.id}
          className={`alert ${ALERT_CLASSES[toast.level]} shadow-lg max-w-sm`}
          role="alert"
        >
          <span className="text-lg">{ALERT_ICONS[toast.level]}</span>
          <span className="text-sm">{toast.message}</span>
          <button
            className="btn btn-ghost btn-xs"
            onClick={() => handleDismiss(toast.id)}
            aria-label="Dismiss notification"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}
