"use client";

import { ChatWorkspace } from "@/components/chat/ChatWorkspace";
import { DocumentRail } from "@/components/layout/DocumentRail";
import { Header } from "@/components/layout/Header";
import { useDocuments } from "@/hooks/useDocuments";

export function AppShell() {
  const { documents, notice, loadError, loading } = useDocuments();

  return (
    <div className="flex min-h-screen flex-col">
      <a className="skip-link" href="#chat-workspace">
        Skip to assistant
      </a>
      <Header document={documents[0] ?? null} />
      {loadError ? (
        <div className="border-b border-crimson/30 bg-crimson-soft px-4 py-2 text-sm text-crimson-dark">
          {loadError}
        </div>
      ) : null}
      <div className="mx-auto flex min-h-0 w-full max-w-[1120px] flex-1">
        <DocumentRail documents={documents} notice={notice} />
        <main className="flex min-h-[calc(100vh-64px)] min-w-0 flex-1 flex-col">
          {loading ? (
            <p className="px-6 py-10 text-sm text-ink-muted">Loading indexed documents…</p>
          ) : (
            <ChatWorkspace documents={documents} />
          )}
        </main>
      </div>
    </div>
  );
}
