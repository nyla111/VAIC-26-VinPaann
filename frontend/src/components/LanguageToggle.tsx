"use client";

import { useLanguage } from "@/context/LanguageContext";

export function LanguageToggle() {
  const { language, setLanguage, dictionary } = useLanguage();
  return (
    <div className="language-toggle" aria-label={dictionary.language}>
      <button type="button" className={language === "vi" ? "active" : ""} onClick={() => setLanguage("vi")}>VI</button>
      <button type="button" className={language === "en" ? "active" : ""} onClick={() => setLanguage("en")}>EN</button>
    </div>
  );
}
