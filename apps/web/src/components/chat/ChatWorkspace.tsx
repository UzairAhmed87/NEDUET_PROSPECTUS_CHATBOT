"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { ChatMessage } from "@/components/chat/ChatMessage";
import { Composer } from "@/components/chat/Composer";
import { EmptyState } from "@/components/chat/EmptyState";
import { suggestedQuestions } from "@/features/assistant/suggestedQuestions";
import { ApiRequestError, sendChat } from "@/lib/api";
import type { ChatMessage as ChatMessageModel, DocumentSummary } from "@/types/api";

function newId(): string {
  return crypto.randomUUID();
}

export function ChatWorkspace({ documents }: { documents: DocumentSummary[] }) {
  const [messages, setMessages] = useState<ChatMessageModel[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const lastQuestion = useRef<string>("");
  const suggestions = useMemo(() => suggestedQuestions(documents), [documents]);
  const noCorpus = documents.length === 0;
  const scroller = useRef<HTMLDivElement>(null);
  const nearBottom = useRef(true);

  useEffect(() => {
    const element = scroller.current;
    if (element && nearBottom.current) {
      element.scrollTo({ top: element.scrollHeight, behavior: "smooth" });
    }
  }, [messages]);

  async function ask(question: string) {
    if (busy) return;
    nearBottom.current = true;
    lastQuestion.current = question;
    const userMessage: ChatMessageModel = { id: newId(), role: "user", content: question };
    const pendingId = newId();
    setMessages((current) => [
      ...current,
      userMessage,
      { id: pendingId, role: "assistant", content: "", pending: true },
    ]);
    setBusy(true);
    try {
      const response = await sendChat({
        question,
        conversation_id: conversationId,
      });
      setConversationId(response.conversation_id);
      setMessages((current) =>
        current.map((message) =>
          message.id === pendingId
            ? {
                id: pendingId,
                role: "assistant",
                content: response.answer,
                citations: response.citations,
                insufficient_evidence: response.insufficient_evidence,
                limitation: response.limitation,
              }
            : message,
        ),
      );
    } catch (error) {
      const message =
        error instanceof ApiRequestError
          ? error.message
          : "The assistant could not complete that request.";
      setMessages((current) =>
        current.map((item) => (item.id === pendingId ? { ...item, pending: false, error: message } : item)),
      );
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setMessages([]);
    setConversationId(null);
    lastQuestion.current = "";
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div
        id="chat-workspace"
        ref={scroller}
        onScroll={(event) => {
          const element = event.currentTarget;
          nearBottom.current = element.scrollHeight - element.scrollTop - element.clientHeight < 120;
        }}
        className="min-h-0 flex-1 overflow-y-auto px-4 py-4 sm:px-6"
      >
        {messages.length === 0 ? (
          <EmptyState questions={suggestions} onSelect={ask} disabled={busy || noCorpus} />
        ) : (
          <div className="mx-auto flex max-w-[40rem] flex-col gap-5 py-2">
            <div className="flex justify-end">
              <button
                type="button"
                onClick={reset}
                className="text-[11px] uppercase tracking-[0.14em] text-ink-faint hover:text-ink"
              >
                Start new chat
              </button>
            </div>
            {messages.map((message) => (
              <ChatMessage
                key={message.id}
                message={message}
                onRetry={message.error ? () => ask(lastQuestion.current) : undefined}
              />
            ))}
          </div>
        )}
        {noCorpus && messages.length === 0 ? (
          <p className="mx-auto max-w-[40rem] text-sm text-crimson">
            No documents are indexed yet, so the assistant cannot answer. Ingest an official prospectus first.
          </p>
        ) : null}
      </div>
      <Composer disabled={busy || noCorpus} onSubmit={ask} />
    </div>
  );
}
