"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import { Header } from "@/components/layout/Header";
import { ingestDocument } from "@/lib/api";

export default function AdminPage() {
  const [adminKey, setAdminKey] = useState("");
  const [title, setTitle] = useState("");
  const [year, setYear] = useState("");
  const [replace, setReplace] = useState(false);
  const [verified, setVerified] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fileInput = form.elements.namedItem("file") as HTMLInputElement;
    const file = fileInput.files?.[0];
    if (!file) {
      setError("Choose a PDF first.");
      return;
    }
    const payload = new FormData();
    payload.append("file", file);
    if (title.trim()) payload.append("title", title.trim());
    if (year.trim()) payload.append("academic_year", year.trim());
    payload.append("replace", String(replace));
    payload.append("authenticity_verified", String(verified));
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const result = (await ingestDocument(payload, adminKey)) as {
        document?: { title?: string; chunk_count?: number };
        warnings?: string[];
      };
      setStatus(
        `Indexed “${result.document?.title ?? file.name}” with ${result.document?.chunk_count ?? 0} chunks.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ingest failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen">
      <Header document={null} />
      <main className="mx-auto max-w-[640px] px-4 py-10">
        <p className="text-[11px] uppercase tracking-[0.16em] text-crimson">Operator only</p>
        <h1 className="mt-2 font-serif text-3xl text-ink">Ingest a prospectus</h1>
        <p className="mt-3 text-sm leading-relaxed text-ink-muted">
          This form calls the protected FastAPI ingest endpoint. The admin key stays in your browser
          and is sent as <code>X-Admin-Key</code>. Do not mark authenticity as verified unless you
          have checked the file against an official NED source.
        </p>
        <form onSubmit={onSubmit} className="mt-8 space-y-4 border border-rule bg-paper-raised p-5">
          <label className="block text-sm">
            Admin key
            <input
              type="password"
              required
              value={adminKey}
              onChange={(event) => setAdminKey(event.target.value)}
              className="mt-1 w-full border border-rule bg-paper px-3 py-2"
              autoComplete="off"
            />
          </label>
          <label className="block text-sm">
            PDF file
            <input type="file" name="file" accept="application/pdf,.pdf" required className="mt-1 block w-full text-sm" />
          </label>
          <label className="block text-sm">
            Title
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              className="mt-1 w-full border border-rule bg-paper px-3 py-2"
              placeholder="Undergraduate Prospectus"
            />
          </label>
          <label className="block text-sm">
            Academic year
            <input
              value={year}
              onChange={(event) => setYear(event.target.value)}
              className="mt-1 w-full border border-rule bg-paper px-3 py-2"
              placeholder="2024-25"
            />
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={replace} onChange={(event) => setReplace(event.target.checked)} />
            Replace if this file hash is already indexed
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={verified} onChange={(event) => setVerified(event.target.checked)} />
            I have verified this is an authentic official prospectus
          </label>
          <button
            type="submit"
            disabled={busy}
            className="bg-crimson px-4 py-2 text-sm uppercase tracking-[0.12em] text-paper-raised hover:bg-crimson-dark disabled:opacity-50"
          >
            {busy ? "Indexing…" : "Ingest PDF"}
          </button>
          {status ? <p className="text-sm text-navy">{status}</p> : null}
          {error ? <p className="text-sm text-crimson">{error}</p> : null}
        </form>
        <p className="mt-6 text-sm">
          <Link href="/" className="text-crimson underline underline-offset-2">
            Back to assistant
          </Link>
        </p>
      </main>
    </div>
  );
}
