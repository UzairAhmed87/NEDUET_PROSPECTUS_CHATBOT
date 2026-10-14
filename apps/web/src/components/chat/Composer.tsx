"use client";

import { ArrowUp } from "lucide-react";
import { FormEvent, KeyboardEvent, useId, useState } from "react";

export function Composer({
  disabled,
  onSubmit,
}: {
  disabled: boolean;
  onSubmit: (question: string) => void;
}) {
  const [value, setValue] = useState("");
  const fieldId = useId();

  function submit() {
    const question = value.trim();
    if (!question || disabled) {
      return;
    }
    onSubmit(question);
    setValue("");
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    submit();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form onSubmit={handleSubmit} className="border-t border-rule bg-paper-raised px-4 py-3 sm:px-6">
      <label htmlFor={fieldId} className="sr-only">
        Ask a question about the indexed prospectus
      </label>
      <div className="mx-auto flex max-w-[40rem] items-end gap-2">
        <textarea
          id={fieldId}
          rows={2}
          value={value}
          disabled={disabled}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about admissions, programmes, or fees"
          className="min-h-[3rem] w-full resize-none border border-rule bg-paper px-3 py-2 text-[15px] text-ink placeholder:text-ink-faint disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={disabled || value.trim().length === 0}
          aria-label="Send question"
          className="flex h-11 w-11 shrink-0 items-center justify-center bg-crimson text-paper-raised hover:bg-crimson-dark disabled:bg-paper-inset disabled:text-ink-faint"
        >
          <ArrowUp className="h-5 w-5" />
        </button>
      </div>
      <p className="mx-auto mt-2 max-w-[40rem] text-[11px] text-ink-faint">
        Answers come from the prospectus and are not an official university decision.
      </p>
    </form>
  );
}
