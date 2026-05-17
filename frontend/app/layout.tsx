import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "GithubGuide",
  description: "Local-first trace-based onboarding for GitHub repositories"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

