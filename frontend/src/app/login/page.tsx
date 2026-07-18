"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

export default function LoginPage() {
  const router = useRouter();
  const { user, loading, login } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!loading && user) router.replace(`/${user.role}`);
  }, [loading, router, user]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    const form = new FormData(event.currentTarget);
    try {
      await login(String(form.get("email")), String(form.get("password")));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Đăng nhập thất bại.");
      setSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-panel">
        <h1>VAIC Logistics</h1>
        <p>Đăng nhập dashboard điều phối logistics ĐBSCL.</p>
        {error ? <div className="alert">{error}</div> : null}
        <form onSubmit={onSubmit} className="form-stack">
          <label>
            Email
            <input name="email" type="email" required autoComplete="email" />
          </label>
          <label>
            Password
            <input name="password" type="password" required autoComplete="current-password" />
          </label>
          <button type="submit" disabled={submitting}>
            {submitting ? "Đang đăng nhập..." : "Đăng nhập"}
          </button>
        </form>
        <div className="demo-users">
          <strong>Tài khoản demo</strong>
          <span>enterprise1@vaic.vn / demo123</span>
          <span>logistics1@vaic.vn / demo123</span>
          <span>admin1@vaic.vn / demo123</span>
        </div>

      </section>
    </main>
  );
}
