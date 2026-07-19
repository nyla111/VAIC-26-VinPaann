"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { useLanguage } from "@/context/LanguageContext";
import { Brand } from "@/components/Brand";
import { LanguageToggle } from "@/components/LanguageToggle";

export default function LoginPage() {
  const router = useRouter();
  const { user, loading, login } = useAuth();
  const { dictionary } = useLanguage();
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
        <div className="login-brand-row"><Brand /><LanguageToggle /></div>
        <h1>{dictionary.login}</h1>
        <p>{dictionary.loginDescription}</p>
        {error ? <div className="alert">{error}</div> : null}
        <form onSubmit={onSubmit} className="form-stack">
          <label>
            {dictionary.email}
            <input name="email" type="email" required autoComplete="email" />
          </label>
          <label>
            {dictionary.password}
            <input name="password" type="password" required autoComplete="current-password" />
          </label>
          <button type="submit" disabled={submitting}>
            {submitting ? dictionary.loading : dictionary.login}
          </button>
        </form>
        <div className="demo-users">
          <strong>{dictionary.demoAccounts}</strong>
          <span>enterprise1@vaic.vn / demo123</span>
          <span>logistics1@vaic.vn / demo123</span>
          <span>admin1@vaic.vn / demo123</span>
        </div>

      </section>
    </main>
  );
}
