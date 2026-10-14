import type { DocumentSummary } from "@/types/api";

const FALLBACK = [
  "What undergraduate programmes are listed in the prospectus?",
  "What does the prospectus say about admission eligibility?",
  "Are scholarship or fee details mentioned in the prospectus?",
  "What does the prospectus say about the admission procedure?",
];

export function suggestedQuestions(documents: DocumentSummary[]): string[] {
  const headings = documents.flatMap((document) => document.headings).filter(Boolean);
  if (headings.length === 0) {
    return FALLBACK;
  }

  const mapped: string[] = [];
  for (const heading of headings) {
    const upper = heading.toUpperCase();
    let question: string;
    if (upper.includes("PROGRAMME") || upper.includes("PROGRAM")) {
      question = "Which undergraduate programmes are listed in the prospectus?";
    } else if (upper.includes("ELIGIB")) {
      question = "What does the prospectus say about admission eligibility?";
    } else if (upper.includes("FEE") || upper.includes("SCHOLAR")) {
      question = "Are scholarship or fee details mentioned in the prospectus?";
    } else {
      const clean = heading.replace(/\s+/g, " ").trim();
      question = `What does the prospectus say about ${clean}?`;
    }
    if (!mapped.includes(question)) {
      mapped.push(question);
    }
  }

  for (const fallback of FALLBACK) {
    if (mapped.length >= 4) {
      break;
    }
    const overlap = mapped.some(
      (existing) => existing.toLowerCase().includes("programme") && fallback.toLowerCase().includes("programme"),
    );
    if (!mapped.includes(fallback) && !overlap) {
      mapped.push(fallback);
    }
  }
  return mapped.slice(0, 4);
}

export { FALLBACK as FALLBACK_QUESTIONS };
