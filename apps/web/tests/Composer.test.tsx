import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Composer } from "@/components/chat/Composer";
import { EmptyState } from "@/components/chat/EmptyState";
import { ErrorState } from "@/components/chat/ErrorState";

describe("chat UI states", () => {
  it("disables send when composer is empty or disabled", () => {
    render(<Composer disabled onSubmit={vi.fn()} />);
    expect(screen.getByLabelText("Send question")).toBeDisabled();
    expect(screen.getByLabelText("Ask a question about the indexed prospectus")).toBeDisabled();
  });

  it("renders suggested questions as buttons", () => {
    render(
      <EmptyState
        questions={["What undergraduate programmes are listed in the indexed prospectus?"]}
        onSelect={vi.fn()}
        disabled={false}
      />,
    );
    expect(
      screen.getByRole("button", {
        name: "What undergraduate programmes are listed in the indexed prospectus?",
      }),
    ).toBeInTheDocument();
  });

  it("shows recoverable error copy", () => {
    render(<ErrorState message="Cannot reach the prospectus API." onRetry={vi.fn()} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Cannot reach the prospectus API.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});
