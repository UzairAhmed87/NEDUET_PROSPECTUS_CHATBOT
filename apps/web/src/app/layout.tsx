import type { Metadata } from "next";
import { Newsreader, Source_Sans_3 } from "next/font/google";

import { SplashScreen } from "@/components/ui/SplashScreen";

import "./globals.css";

const serif = Newsreader({
  subsets: ["latin"],
  variable: "--font-serif",
  display: "swap",
});

const sans = Source_Sans_3({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "NED Prospectus Assistant",
  description:
    "Ask questions grounded in ingested NED University of Engineering & Technology prospectus documents.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${serif.variable} ${sans.variable} font-sans antialiased`}>
        <SplashScreen />
        {children}
      </body>
    </html>
  );
}
