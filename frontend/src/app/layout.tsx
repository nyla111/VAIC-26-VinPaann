import type { Metadata } from "next";
import { AuthProvider } from "@/context/AuthContext";
import { LanguageProvider } from "@/context/LanguageContext";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "DeltaFlow AI",
  description: "AI logistics orchestration for the Mekong Delta",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi">
      <body>
        <LanguageProvider><AuthProvider>{children}</AuthProvider></LanguageProvider>
      </body>
    </html>
  );
}
