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
  const { dictionary, language } = useLanguage();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    if (!loading && user) router.replace(`/${user.role}`);
  }, [loading, router, user]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Đăng nhập thất bại.");
      setSubmitting(false);
    }
  }

  const handleQuickFill = (roleEmail: string) => {
    setEmail(roleEmail);
    setPassword("demo123");
  };

  const bannerText = language === "vi" ? {
    title: "Tối Ưu Hóa Logistics Bằng Trí Tuệ Nhân Tạo",
    desc: "DeltaFlow AI là nền tảng quản trị và điều phối chuỗi cung ứng nông sản thông minh cho vùng Đồng bằng sông Cửu Long, tích hợp dữ liệu thủy văn và dự báo thời gian thực.",
    footer: "© 2026 VinUniversity AgTech Center. Tất cả các quyền được bảo lưu."
  } : {
    title: "AI-Powered Logistics Orchestration",
    desc: "DeltaFlow AI is an intelligent supply chain orchestration platform for agricultural products in the Mekong Delta, integrating real-time hydrological and routing data.",
    footer: "© 2026 VinUniversity AgTech Center. All rights reserved."
  };

  return (
    <main className="login-page">
      {/* Left panel for branding & banner */}
      <section className="login-banner">
        <div className="login-banner-header">
          <Brand />
        </div>
        <div className="login-banner-body">
          <h2>{bannerText.title}</h2>
          <p>{bannerText.desc}</p>
        </div>
        <div className="login-banner-footer">
          {bannerText.footer}
        </div>
      </section>

      {/* Right panel for login form */}
      <section className="login-container">
        <div className="login-panel">
          <div className="login-brand-row">
            <div className="block md:hidden">
              <Brand />
            </div>
            <div style={{ marginLeft: "auto" }}>
              <LanguageToggle />
            </div>
          </div>
          <h1>{dictionary.login}</h1>
          <p>{dictionary.loginDescription}</p>
          
          {error ? (
            <div className="alert">
              <span>⚠️</span>
              <div>{error}</div>
            </div>
          ) : null}
          
          <form onSubmit={onSubmit} className="form-stack">
            <label>
              {dictionary.email}
              <input
                name="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="email@example.com"
              />
            </label>
            <label>
              {dictionary.password}
              <input
                name="password"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
              />
            </label>
            <button type="submit" disabled={submitting}>
              {submitting ? dictionary.loading : dictionary.login}
            </button>
          </form>

          <div className="login-quickfill">
            <strong>{dictionary.demoAccounts}</strong>
            <div className="quickfill-grid">
              <button 
                type="button" 
                className="quickfill-btn" 
                onClick={() => handleQuickFill("enterprise1@vaic.vn")}
              >
                🏢 Enterprise Partner <span>enterprise1@vaic.vn</span>
              </button>
              <button 
                type="button" 
                className="quickfill-btn" 
                onClick={() => handleQuickFill("logistics1@vaic.vn")}
              >
                🚛 Logistics Fleet <span>logistics1@vaic.vn</span>
              </button>
              <button 
                type="button" 
                className="quickfill-btn" 
                onClick={() => handleQuickFill("admin1@vaic.vn")}
              >
                ⚙️ Platform Admin <span>admin1@vaic.vn</span>
              </button>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
