import type { Metadata } from "next";
import { Atkinson_Hyperlegible, Literata } from "next/font/google";
import "./globals.css";

const serif = Literata({ subsets: ["latin"], axes: ["opsz"], variable: "--serif" });
const sans = Atkinson_Hyperlegible({
  subsets: ["latin"],
  weight: ["400", "700"],
  variable: "--sans",
});

export const metadata: Metadata = {
  title: "CourseLens",
  description: "Ask the course readings. Every answer shows its sources.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${serif.variable} ${sans.variable}`}>
      <body>{children}</body>
    </html>
  );
}
