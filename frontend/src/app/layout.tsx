import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Company Lens",
  description:
    "AI-powered corporate-banking client-acquisition intelligence platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-theme="companylens">
      <body className="bg-base-200">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
