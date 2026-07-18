import type { Metadata } from "next";
import { AuthProvider } from "@/context/AuthContext";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "VAIC Dashboard",
  description: "VAIC logistics dashboard",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
