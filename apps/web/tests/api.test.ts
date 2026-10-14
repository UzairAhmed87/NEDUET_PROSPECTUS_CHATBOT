import { describe, expect, it } from "vitest";

import { FALLBACK_QUESTIONS, suggestedQuestions } from "@/features/assistant/suggestedQuestions";
import type { DocumentSummary } from "@/types/api";

const sample: DocumentSummary = {
  document_id: "doc-1",
  title: "Fixture",
  source_filename: "fixture.pdf",
  document_version: null,
  academic_year: "2024-25",
  authenticity_verified: false,
  page_count: 5,
  chunk_count: 8,
  sha256: "abc",
  ingested_at: "2024-01-01T00:00:00Z",
  headings: ["ADMISSION ELIGIBILITY", "FEE STRUCTURE"],
  ocr_page_count: 0,
  empty_page_count: 1,
};

describe("suggestedQuestions", () => {
  it("uses fallback prompts when no headings exist", () => {
    expect(suggestedQuestions([])).toEqual(FALLBACK_QUESTIONS);
  });

  it("builds questions from extracted headings without inventing facts", () => {
    const questions = suggestedQuestions([sample]);
    expect(questions.join(" ").toLowerCase()).toContain("eligibility");
    expect(questions.join(" ")).not.toMatch(/\d{2}%/);
  });
});
