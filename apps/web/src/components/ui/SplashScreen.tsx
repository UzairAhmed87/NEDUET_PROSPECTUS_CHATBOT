"use client";

import { useEffect, useState } from "react";

import { Mark } from "@/components/ui/Mark";

const SESSION_KEY = "ned-splash-seen";
const VISIBLE_MS = 2300;
const FADE_MS = 500;

export function SplashScreen() {
  const [phase, setPhase] = useState<"visible" | "leaving" | "gone">("visible");

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (sessionStorage.getItem(SESSION_KEY)) {
      setPhase("gone");
      return;
    }
    sessionStorage.setItem(SESSION_KEY, "1");
    const leave = window.setTimeout(() => setPhase("leaving"), reduced ? 400 : VISIBLE_MS);
    const remove = window.setTimeout(() => setPhase("gone"), (reduced ? 400 : VISIBLE_MS) + FADE_MS);
    return () => {
      window.clearTimeout(leave);
      window.clearTimeout(remove);
    };
  }, []);

  if (phase === "gone") return null;

  return (
    <div
      role="status"
      aria-label="Loading NED Prospectus Assistant"
      onClick={() => setPhase("gone")}
      className={`splash fixed inset-0 z-[100] flex flex-col items-center justify-center bg-[#F6F1E7] transition-opacity duration-500 ${
        phase === "leaving" ? "pointer-events-none opacity-0" : "opacity-100"
      }`}
    >
      <div className="splash-mark">
        <Mark className="h-16 w-16 shadow-[0_12px_30px_-14px_rgba(127,20,36,0.7)]" />
      </div>
      <p className="splash-title mt-6 font-serif text-[1.9rem] leading-tight text-[#211D19]">
        Prospectus Assistant
      </p>
      <p className="splash-sub mt-2 text-[11px] uppercase tracking-[0.24em] text-[#777064]">
        NED University of Engineering &amp; Technology
      </p>
      <span className="splash-line mt-6 block h-px w-40 origin-left bg-[#A6192E]" aria-hidden="true" />
    </div>
  );
}
