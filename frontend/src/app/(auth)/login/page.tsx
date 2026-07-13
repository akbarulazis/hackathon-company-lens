"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth, ApiRequestError } from "@/hooks/useAuth";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await login(username, password);
      router.push("/workspaces");
    } catch (err) {
      if (err instanceof ApiRequestError) {
        if (err.status === 429) {
          setError("Too many failed attempts. Please try again in 15 minutes.");
        } else if (err.status === 401) {
          setError("Invalid credentials.");
        } else {
          setError(err.message || "An unexpected error occurred.");
        }
      } else {
        setError("Unable to connect to the server.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div
      className="flex min-h-screen items-center justify-center px-4"
      style={{ backgroundColor: "#f5f1ec" }}
    >
      <div className="w-full max-w-[420px]">
        {/* Brand */}
        <div className="text-center mb-10">
          <h1
            className="text-[32px] font-medium"
            style={{ color: "#111111", letterSpacing: "-0.8px" }}
          >
            Company Lens
          </h1>
          <p className="mt-2 text-[16px]" style={{ color: "#626260" }}>
            Sign in to your account
          </p>
        </div>

        {/* Card */}
        <div
          className="p-8"
          style={{
            backgroundColor: "#ffffff",
            borderRadius: "16px",
            border: "1px solid #d3cec6",
          }}
        >
          {/* Error */}
          {error && (
            <div
              className="mb-5 px-4 py-3"
              style={{
                backgroundColor: "#fef2f2",
                border: "1px solid #fecaca",
                borderRadius: "8px",
              }}
            >
              <p className="text-[14px]" style={{ color: "#b91c1c" }}>
                {error}
              </p>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            {/* Username */}
            <div className="mb-5">
              <label
                htmlFor="username"
                className="block text-[14px] font-medium mb-2"
                style={{ color: "#111111" }}
              >
                Username
              </label>
              <input
                id="username"
                type="text"
                placeholder="Enter your username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoComplete="username"
                disabled={isSubmitting}
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  fontSize: "15px",
                  color: "#111111",
                  backgroundColor: "#ffffff",
                  border: "1px solid #d3cec6",
                  borderRadius: "8px",
                  outline: "none",
                  transition: "border-color 0.15s",
                }}
                onFocus={(e) => (e.target.style.borderColor = "#111111")}
                onBlur={(e) => (e.target.style.borderColor = "#d3cec6")}
              />
            </div>

            {/* Password */}
            <div className="mb-6">
              <label
                htmlFor="password"
                className="block text-[14px] font-medium mb-2"
                style={{ color: "#111111" }}
              >
                Password
              </label>
              <input
                id="password"
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                disabled={isSubmitting}
                style={{
                  width: "100%",
                  padding: "10px 14px",
                  fontSize: "15px",
                  color: "#111111",
                  backgroundColor: "#ffffff",
                  border: "1px solid #d3cec6",
                  borderRadius: "8px",
                  outline: "none",
                  transition: "border-color 0.15s",
                }}
                onFocus={(e) => (e.target.style.borderColor = "#111111")}
                onBlur={(e) => (e.target.style.borderColor = "#d3cec6")}
              />
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={isSubmitting || !username || !password}
              style={{
                width: "100%",
                padding: "11px 18px",
                fontSize: "15px",
                fontWeight: 500,
                color: "#ffffff",
                backgroundColor: isSubmitting ? "#333333" : "#111111",
                borderRadius: "8px",
                border: "none",
                cursor:
                  isSubmitting || !username || !password
                    ? "not-allowed"
                    : "pointer",
                opacity: isSubmitting || !username || !password ? 0.6 : 1,
                transition: "background-color 0.15s, opacity 0.15s",
              }}
              onMouseEnter={(e) => {
                if (!isSubmitting) e.currentTarget.style.backgroundColor = "#000000";
              }}
              onMouseLeave={(e) => {
                if (!isSubmitting) e.currentTarget.style.backgroundColor = "#111111";
              }}
            >
              {isSubmitting ? "Signing in..." : "Sign in"}
            </button>
          </form>
        </div>

        {/* Footer */}
        <p className="text-center text-[14px] mt-8" style={{ color: "#626260" }}>
          Don&apos;t have an account?{" "}
          <Link
            href="/register"
            className="hover:underline"
            style={{ color: "#111111", fontWeight: 500 }}
          >
            Create one
          </Link>
        </p>
      </div>
    </div>
  );
}
