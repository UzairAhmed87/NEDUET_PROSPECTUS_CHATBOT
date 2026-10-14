import { ArrowRight } from "lucide-react";

export function EmptyState({
  questions,
  onSelect,
  disabled,
}: {
  questions: string[];
  onSelect: (question: string) => void;
  disabled: boolean;
}) {
  return (
    <div className="mx-auto max-w-[42rem] px-1 py-10 sm:py-16">
      <div className="animate-fade-up">
        <h1 className="font-serif text-[2.1rem] leading-[1.1] text-ink sm:text-[2.75rem]">
          Ask the prospectus.
        </h1>
        <p className="mt-4 max-w-[36rem] text-[15px] leading-relaxed text-ink-muted">
          Answers come only from the prospectus, with page references.
        </p>
      </div>
      <ul className="mt-10 grid gap-3 sm:grid-cols-2">
        {questions.map((question, index) => (
          <li key={question} className="animate-fade-up" style={{ animationDelay: `${120 + index * 70}ms` }}>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onSelect(question)}
              className="group flex h-full w-full items-start justify-between gap-4 border border-rule bg-paper-raised px-4 py-4 text-left text-[15px] leading-snug text-ink transition-[border-color,transform,box-shadow] duration-200 hover:-translate-y-0.5 hover:border-crimson/50 hover:shadow-[0_6px_20px_-12px_rgba(127,20,36,0.35)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-crimson active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0"
            >
              <span>{question}</span>
              <ArrowRight
                aria-hidden="true"
                className="mt-0.5 h-4 w-4 shrink-0 text-crimson transition-transform duration-200 group-hover:translate-x-1"
              />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
