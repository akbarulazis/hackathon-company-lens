"use client";

import { useState, FormEvent, useMemo } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth, ApiRequestError } from "@/hooks/useAuth";

function checkPasswordStrength(password: string) {
  return {
    hasMinLength: password.length >= 8,
    hasUppercase: /[A-Z]/.test(password),
    hasLowercase: /[a-z]/.test(password),
    hasDigit: /\d/.test(password),
    hasSpecial: /[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]/.test(password),
    get isValid() {
      return this.hasMinLength && this.hasUppercase && this.hasLowercase && this.hasDigit && this.hasSpecial;
    },
  };
}

const inputStyle = {
  width: "100%",
  padding: "10px 14px",
  fontSize: "15px",
  color: "#111111",
  backgroundColor: "#ffffff",
  border: "1px solid #d3cec6",
  borderRadius: "8px",
  outline: "none",
  transition: "border-color 0.15s",
};

export default function RegisterPage() {
  const router = useRouter();
  const { register } = useAuth();

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const strength = useMemo(() => checkPasswordStrength(password), [password]);
  const canSubmit = /^[a-zA-Z0-9_-]{3,50}$/.test(username) && email.includes("@") && strength.isValid && !isSubmitting;

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      await register(username, email, password);
      router.push("/login?registered=true");
    } catch (err) {
      if (err instanceof ApiRequestError) {
        setError((err.detail as { detail?: string })?.detail ?? err.message);
      } else {
        setError("Unable to connect to the server.");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4" style={{ backgroundColor: "#f5f1ec" }}>
      <div className="w-full max-w-[420px]">
        {/* Brand */}
        <div className="text-center mb-10">
          <h1 className="text-[32px] font-medium" style={{ color: "#111111", letterSpacing: "-0.8px" }}>
            Create Account
          </h1>
          <p className="mt-2 text-[16px]" style={{ color: "#626260" }}>
            Join Company Lens to start researching
          </p>
        </div>

        {/* Card */}
        <div className="p-8" style={{ backgroundColor: "#ffffff", borderRadius: "16px", border: "1px solid #d3cec6" }}>
          {error && (
            <div className="mb-5 px-4 py-3" style={{ backgroundColor: "#fef2f2", border: "1px solid #fecaca", borderRadius: "8px" }}>
              <p className="text-[14px]" style={{ color: "#b91c1c" }}>{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="mb-5">
              <label htmlFor="username" className="block text-[14px] font-medium mb-2" style={{ color: "#111111" }}>Username</label>
              <input
                id="username"
                type="text"
                placeholder="3-50 characters (letters, digits, _, -)"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                disabled={isSubmitting}
                style={inputStyle}
                onFocus={(e) => (e.target.style.borderColor = "#111111")}
                onBlur={(e) => (e.target.style.borderColor = "#d3cec6")}
              />
            </div>

            <div className="mb-5">
              <label htmlFor="email" className="block text-[14px] font-medium mb-2" style={{ color: "#111111" }}>Email</label>
              <input
                id="email"
                type="email"
                placeholder="your@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                disabled={isSubmitting}
                style={inputStyle}
                onFocus={(e) => (e.target.style.borderColor = "#111111")}
                onBlur={(e) => (e.target.style.borderColor = "#d3cec6")}
              />
            </div>

            <div className="mb-6">
              <label htmlFor="password" className="block text-[14px] font-medium mb-2" style={{ color: "#111111" }}>Password</label>
              <input
                id="password"
                type="password"
                placeholder="At least 8 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                disabled={isSubmitting}
                style={inputStyle}
                onFocus={(e) => (e.target.style.borderColor = "#111111")}
                onBlur={(e) => (e.target.style.borderColor = "#d3cec6")}
              />
              {password.length > 0 && (
                <div className="mt-2 space-y-1">
                  {[
                    { met: strength.hasMinLength, label: "8+ characters" },
                    { met: strength.hasUppercase, label: "Uppercase" },
                    { met: strength.hasLowercase, label: "Lowercase" },
                    { met: strength.hasDigit, label: "Digit" },
                    { met: strength.hasSpecial, label: "Special char" },
                  ].map((rule) => (
                    <p key={rule.label} className="text-[12px]" style={{ color: rule.met ? "#16a34a" : "#9c9fa5" }}>
                      {rule.met ? "✓" : "○"} {rule.label}
                    </p>
                  ))}
                </div>
              )}
            </div>

            <button
              type="submit"
              disabled={!canSubmit}
              style={{
                width: "100%",
                padding: "11px 18px",
                fontSize: "15px",
                fontWeight: 500,
                color: "#ffffff",
                backgroundColor: "#111111",
                borderRadius: "8px",
                border: "none",
                cursor: canSubmit ? "pointer" : "not-allowed",
                opacity: canSubmit ? 1 : 0.5,
                transition: "background-color 0.15s, opacity 0.15s",
              }}
            >
              {isSubmitting ? "Creating..." : "Create Account"}
            </button>
          </form>
        </div>

        <p className="text-center text-[14px] mt-8" style={{ color: "#626260" }}>
          Already have an account?{" "}
          <Link href="/login" className="hover:underline" style={{ color: "#111111", fontWeight: 500 }}>
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
