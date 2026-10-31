import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import TraditionNotes from "@/components/TraditionNotes";
import type { TraditionNote } from "@/lib/api";

afterEach(cleanup);

const note = (over: Partial<TraditionNote> = {}): TraditionNote => ({
  tag: "fawu",
  note: "中醫傳統說法將蝦列為發物。",
  source_title: "選擇第547期",
  source_url: "https://www.consumer.org.hk/x",
  draft: false,
  ...over,
});

describe("TraditionNotes", () => {
  it("renders nothing when there are no notes", () => {
    const { container } = render(<TraditionNotes notes={[]} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders the card title and the fixed non-evidence disclaimer", () => {
    render(<TraditionNotes notes={[note()]} />);
    expect(screen.getByText("傳統說法（非實證）")).toBeTruthy();
    expect(
      screen.getByText(/未必有現代臨床研究支持，不影響本站評級/)
    ).toBeTruthy();
  });

  it("groups notes by tag with labelled chips", () => {
    render(
      <TraditionNotes
        notes={[
          note({ note: "發物說法一", tag: "fawu" }),
          note({ note: "寒涼說法一", tag: "cool" }),
          note({ note: "發物說法二", tag: "fawu" }),
        ]}
      />
    );
    expect(screen.getByText("發物")).toBeTruthy();
    expect(screen.getByText("寒涼")).toBeTruthy();
    expect(screen.getByText("發物說法一")).toBeTruthy();
    expect(screen.getByText("發物說法二")).toBeTruthy();
    expect(screen.getByText("寒涼說法一")).toBeTruthy();
  });

  it("labels unknown tags as 其他", () => {
    render(<TraditionNotes notes={[note({ tag: "mystery" })]} />);
    expect(screen.getByText("其他")).toBeTruthy();
  });

  it("shows 待審核 badge only on draft notes", () => {
    render(
      <TraditionNotes
        notes={[note({ draft: true }), note({ note: "已審核內容", draft: false })]}
      />
    );
    expect(screen.getAllByText("待審核")).toHaveLength(1);
  });

  it("renders source_title as an external link with safe attrs", () => {
    render(<TraditionNotes notes={[note()]} />);
    const link = screen.getByRole("link", { name: "選擇第547期" });
    expect(link.getAttribute("href")).toBe("https://www.consumer.org.hk/x");
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("never uses rating colours", () => {
    const { container } = render(<TraditionNotes notes={[note()]} />);
    expect(container.innerHTML).not.toMatch(
      /suitable|caution|trigger|--color-suitable/
    );
  });
});
