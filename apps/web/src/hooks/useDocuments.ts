"use client";

import { useEffect, useState } from "react";

import { fetchDocuments } from "@/lib/api";
import type { DocumentListResponse } from "@/types/api";

export function useDocuments() {
  const [data, setData] = useState<DocumentListResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetchDocuments()
      .then((payload) => {
        if (!cancelled) {
          setData(payload);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setLoadError(error instanceof Error ? error.message : "Unable to load documents.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return {
    documents: data?.documents ?? [],
    notice:
      data?.authenticity_notice ??
      "A listed file is not treated as the latest official prospectus unless authenticity has been verified by the operator.",
    loadError,
    loading,
  };
}
