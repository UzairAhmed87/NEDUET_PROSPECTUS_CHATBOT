"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { CitationList } from "@/components/chat/CitationList";
import { ErrorState } from "@/components/chat/ErrorState";
import { LoadingState } from "@/components/chat/LoadingState";
import { cn } from "@/lib/cn";
import type { ChatMessage as ChatMessageModel } from "@/types/api";

export function ChatMessage({
  message,
  onRetry,
}: {
  message: ChatMessageModel;
  onRetry?: () => void;
}) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);

  async function copyAnswer() {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }

  if (isUser) {
    return (
      <article className="animate-fade-up flex justify-end">
        <div className="max-w-[36rem] whitespace-pre-wrap break-words bg-crimson px-4 py-3 text-[15px] leading-relaxed text-paper-raised shadow-[0_6px_18px_-12px_rgba(127,20,36,0.6)]">
          {message.content}
        </div>
      </article>
    );
  }

  return (
    <article className="animate-fade-up max-w-[40rem]">
      <div
        className={cn(
          "border border-rule bg-paper-raised px-4 py-3 text-[15px] leading-relaxed text-ink",
          message.insufficient_evidence && "border-gold/50",
        )}
      >
        {message.pending ? <LoadingState /> : null}
        {message.error ? <ErrorState message={message.error} onRetry={onRetry} /> : null}
        {!message.pending && !message.error ? (
          <>
            <div className="markdown-body">
              <Markdown remarkPlugins={[remarkGfm]}>{message.content}</Markdown>
            </div>
            {message.limitation ? (
              <p className="mt-3 text-xs leading-relaxed text-ink-muted">{message.limitation}</p>
            ) : null}
            <CitationList citations={message.citations ?? []} />
            <div className="mt-3 flex justify-end">
              <button
                type="button"
                onClick={copyAnswer}
                className="inline-flex items-center gap-1.5 text-[11px] uppercase tracking-[0.14em] text-ink-faint hover:text-ink"
              >
                {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                {copied ? "Copied" : "Copy answer"}
              </button>
            </div>
          </>
        ) : null}
      </div>
    </article>
  );
}
