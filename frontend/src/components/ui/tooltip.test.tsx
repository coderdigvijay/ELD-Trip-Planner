import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { Tooltip as LazyTooltip } from "./tooltip";
import { Tooltip } from "./tooltip-impl";

describe("Tooltip", () => {
  it("opens on keyboard focus and closes on Escape, leaving the trigger's own name alone", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content="Zoom the map to the whole route">
        <button type="button">Fit route</button>
      </Tooltip>,
    );
    await user.tab();
    expect(await screen.findByText("Zoom the map to the whole route")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fit route" })).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.queryByText("Zoom the map to the whole route")).not.toBeInTheDocument();
  });

  it("opens on hover after the delay", async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content="Decrease cycle hours by 0.25">
        <button type="button" aria-label="Decrease cycle hours by 0.25">
          -
        </button>
      </Tooltip>,
    );
    await user.hover(screen.getByRole("button"));
    expect(await screen.findByText("Decrease cycle hours by 0.25")).toBeInTheDocument();
  });

  it("renders the child untouched until the chunk has loaded", () => {
    render(
      <LazyTooltip content="Later">
        <button type="button">Go</button>
      </LazyTooltip>,
    );
    expect(screen.getByRole("button", { name: "Go" })).toHaveAttribute("data-has-tooltip");
    expect(screen.queryByText("Later")).not.toBeInTheDocument();
  });
});
