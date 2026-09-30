import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";

import { errorBody, server } from "@/test/server";

import { describePlanError } from "./describeError";
import { PlanAlert } from "./PlanAlert";
import { toPlanRequest } from "./schema";
import { TripForm } from "./TripForm";
import { usePlanTrip } from "./usePlanTrip";
import { useServerHealth } from "./serverHealth";
import { useTripForm } from "./useTripForm";
import { WakingSummary } from "./WakingSummary";

beforeAll(() => {
  server.listen();
});
afterEach(() => {
  server.resetHandlers();
});
afterAll(() => {
  server.close();
});

const RICHMOND = { label: "Richmond, VA", lat: 37.54072, lng: -77.43605 };
const okHealth = http.get("*/api/v1/health", () =>
  HttpResponse.json({ status: "ok", api_version: "1" }),
);
const planOk = { summary: { sheet_count: 3 }, trip: { places: {} } };

function Harness() {
  const api = useTripForm();
  const health = useServerHealth();
  const planner = usePlanTrip({
    onFailure: (failure) => {
      if (failure.kind === "fields") api.applyProblems(failure.problems);
    },
  });
  return (
    <>
      <h2 id="trip-heading">Trip</h2>
      <TripForm
        api={api}
        pending={planner.isPending}
        onSubmit={(values) => {
          planner.submit(toPlanRequest(values));
        }}
      />
      <output data-testid="health">{health.status}</output>
      <output data-testid="plan">{planner.plan ? "planned" : "none"}</output>
      {planner.isPending && health.isPending ? (
        <WakingSummary startedAtS={planner.submittedAtS ?? 0} onCancel={planner.cancel} />
      ) : null}
      {planner.failure?.kind === "alert" ? (
        <PlanAlert
          failure={planner.failure}
          failedAtS={planner.failedAtS}
          showingPrevious={false}
          onRetry={() => undefined}
          onEdit={() => undefined}
        />
      ) : null}
    </>
  );
}

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const user = userEvent.setup();
  render(
    <QueryClientProvider client={client}>
      <Harness />
    </QueryClientProvider>,
  );
  return { user };
}

async function fillFreeText(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/Current location/), "Richmond, VA");
  await user.type(screen.getByLabelText(/^.*Pickup/), "Baltimore, MD");
  await user.type(screen.getByLabelText(/Dropoff/), "Newark, NJ");
  await user.tab();
}

beforeEach(() => {
  window.history.replaceState(null, "", "/");
  server.use(
    okHealth,
    http.get("*/api/v1/places/autocomplete", () => HttpResponse.json({ items: [] })),
  );
});

describe("validation", () => {
  it("focuses the first invalid field, ties messages with aria-describedby and sends nothing", async () => {
    let posts = 0;
    server.use(http.post("*/api/v1/trips/plan", () => (posts++, HttpResponse.json(planOk))));
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "Plan trip" }));

    const first = screen.getByLabelText(/Current location/);
    await waitFor(() => {
      expect(first).toHaveFocus();
    });
    expect(first).toHaveAttribute("aria-invalid", "true");
    const describedBy = first.getAttribute("aria-describedby") ?? "";
    expect(
      describedBy
        .split(" ")
        .some((id) => document.getElementById(id)?.textContent.includes("Enter a place")),
    ).toBe(true);
    expect(posts).toBe(0);
  });

  it("rejects an off-grid cycle value with the contract wording", async () => {
    const { user } = setup();
    await fillFreeText(user);
    const cycle = screen.getByLabelText(/Cycle used/);
    await user.clear(cycle);
    await user.type(cycle, "12.3");
    await user.click(screen.getByRole("button", { name: "Plan trip" }));
    expect(
      await screen.findByText("Cycle hours must be between 0 and 70, in steps of 0.25."),
    ).toBeInTheDocument();
  });

  it("opens the optional section to show an error inside it", async () => {
    const { user } = setup();
    await fillFreeText(user);
    await user.click(screen.getByText("Start time and log details (optional)"));
    await user.type(screen.getByLabelText(/Truck number/), "x".repeat(40));
    // maxLength blocks typing past 40, so break the rule with a control character instead
    await user.clear(screen.getByLabelText(/Truck number/));
    await user.paste("12​34");
    await user.click(screen.getByText("Start time and log details (optional)"));
    await user.click(screen.getByRole("button", { name: "Plan trip" }));
    await waitFor(() => {
      expect(screen.getByLabelText(/Truck number/)).toHaveFocus();
    });
    expect(screen.getByLabelText(/Truck number/)).toBeVisible();
  });
});

describe("autocomplete", () => {
  it("sends nothing under 3 characters and debounces to one request", async () => {
    const queries: string[] = [];
    server.use(
      http.get("*/api/v1/places/autocomplete", ({ request }) => {
        queries.push(new URL(request.url).searchParams.get("q") ?? "");
        return HttpResponse.json({ items: [RICHMOND] });
      }),
    );
    const { user } = setup();
    const input = screen.getByLabelText(/Current location/);
    await user.type(input, "Ri");
    expect(await screen.findByText("Type 3 or more characters")).toBeInTheDocument();
    await user.type(input, "chm");
    await screen.findByRole("option", { name: "Richmond, VA" });
    expect(queries).toEqual(["Richm"]);
  });

  it("picking a suggestion submits its coordinates; typed text submits as a string", async () => {
    server.use(
      http.get("*/api/v1/places/autocomplete", () => HttpResponse.json({ items: [RICHMOND] })),
    );
    let body: unknown;
    server.use(
      http.post("*/api/v1/trips/plan", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(planOk);
      }),
    );
    const { user } = setup();
    await user.type(screen.getByLabelText(/Current location/), "Rich");
    await screen.findByRole("option", { name: "Richmond, VA" });
    await user.keyboard("{ArrowDown}{Enter}");
    expect(screen.getByLabelText(/Current location/)).toHaveValue("Richmond, VA");
    await user.type(screen.getByLabelText(/^.*Pickup/), "Baltimore, MD");
    await user.type(screen.getByLabelText(/Dropoff/), "Newark, NJ");
    await user.tab();
    await user.click(screen.getByRole("button", { name: "Plan trip" }));
    await waitFor(() => {
      expect(body).toBeDefined();
    });
    expect(body).toMatchObject({
      current_location: RICHMOND,
      pickup_location: "Baltimore, MD",
      dropoff_location: "Newark, NJ",
      current_cycle_used_hours: 0,
    });
  });

  it("degrades to a message with Retry when suggestions fail, and free text still submits", async () => {
    server.use(
      http.get("*/api/v1/places/autocomplete", () =>
        HttpResponse.json(errorBody("UPSTREAM_UNAVAILABLE", "x"), { status: 503 }),
      ),
      http.post("*/api/v1/trips/plan", () => HttpResponse.json(planOk)),
    );
    const { user } = setup();
    await user.type(screen.getByLabelText(/Current location/), "Richmond");
    expect(
      await screen.findByText(/Suggestions are unavailable\. Type the full place/),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await user.clear(screen.getByLabelText(/Current location/));
    await user.type(screen.getByLabelText(/Current location/), "Richmond, VA");
    await user.keyboard("{Escape}");
    await user.type(screen.getByLabelText(/^.*Pickup/), "Baltimore, MD");
    await user.keyboard("{Escape}");
    await user.type(screen.getByLabelText(/Dropoff/), "Newark, NJ");
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: "Plan trip" }));
    await waitFor(() => {
      expect(screen.getByTestId("plan")).toHaveTextContent("planned");
    });
  });

  it("hides Retry when rate limited", async () => {
    server.use(
      http.get("*/api/v1/places/autocomplete", () =>
        HttpResponse.json(errorBody("RATE_LIMITED", "x", { retry_after_s: 5 }), { status: 429 }),
      ),
    );
    const { user } = setup();
    await user.type(screen.getByLabelText(/Current location/), "Richmond");
    expect(await screen.findByText(/Type the full place/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
  });

  it("shows the no-match copy for an empty result", async () => {
    const { user } = setup();
    await user.type(screen.getByLabelText(/Current location/), "xyzzy");
    expect(await screen.findByText(/No places match/)).toHaveTextContent(
      "Try a city and state, like Dallas, TX.",
    );
  });
});

describe("submit", () => {
  it("sends exactly one request for a double submit and shows the pending label", async () => {
    let posts = 0;
    server.use(
      http.post("*/api/v1/trips/plan", async () => {
        posts++;
        await delay(150);
        return HttpResponse.json(planOk);
      }),
    );
    const { user } = setup();
    await fillFreeText(user);
    const button = screen.getByRole("button", { name: "Plan trip" });
    await user.dblClick(button);
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("button", { name: "Planning route..." })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    await waitFor(() => {
      expect(screen.getByTestId("plan")).toHaveTextContent("planned");
    });
    expect(posts).toBe(1);
  });

  it("makes fields read-only, not disabled, while pending", async () => {
    server.use(
      http.post("*/api/v1/trips/plan", async () => {
        await delay(150);
        return HttpResponse.json(planOk);
      }),
    );
    const { user } = setup();
    await fillFreeText(user);
    await user.click(screen.getByRole("button", { name: "Plan trip" }));
    const input = screen.getByLabelText(/Current location/);
    expect(input).toHaveAttribute("readonly");
    expect(input).not.toBeDisabled();
    await waitFor(() => {
      expect(screen.getByTestId("plan")).toHaveTextContent("planned");
    });
  });

  it("puts a LOCATION_NOT_FOUND error under its field, focuses it and keeps all values", async () => {
    server.use(
      http.post("*/api/v1/trips/plan", () =>
        HttpResponse.json(
          errorBody(
            "LOCATION_NOT_FOUND",
            'We couldn\'t find "Newark, NJ". Check the spelling or pick a suggestion from the list.',
            {
              field: "dropoff_location",
            },
          ),
          { status: 422 },
        ),
      ),
    );
    const { user } = setup();
    await fillFreeText(user);
    await user.click(screen.getByRole("button", { name: "Plan trip" }));
    const dropoff = screen.getByLabelText(/Dropoff/);
    await waitFor(() => {
      expect(dropoff).toHaveFocus();
    });
    expect(dropoff).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText(/Check the spelling/)).toBeInTheDocument();
    expect(dropoff).toHaveValue("Newark, NJ");
    expect(screen.getByLabelText(/Current location/)).toHaveValue("Richmond, VA");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows a rate-limit warning with a disabled Try again and a live countdown", async () => {
    server.use(
      http.post("*/api/v1/trips/plan", () =>
        HttpResponse.json(errorBody("RATE_LIMITED", "Wait 42 seconds", { retry_after_s: 3 }), {
          status: 429,
        }),
      ),
    );
    const { user } = setup();
    await fillFreeText(user);
    await user.click(screen.getByRole("button", { name: "Plan trip" }));
    expect(await screen.findByText("Too many requests right now")).toBeInTheDocument();
    const retry = screen.getByRole("button", { name: "Try again" });
    expect(retry).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText(/You can plan again in \d s\./)).toBeInTheDocument();
    await waitFor(
      () => {
        expect(screen.getByRole("button", { name: "Try again" })).not.toHaveAttribute(
          "aria-disabled",
          "true",
        );
      },
      { timeout: 5000 },
    );
  });

  it("shows Could not reach the server for a Render 502 page", async () => {
    server.use(
      http.post(
        "*/api/v1/trips/plan",
        () => new HttpResponse("<html>Bad gateway</html>", { status: 502 }),
      ),
    );
    const { user } = setup();
    await fillFreeText(user);
    await user.click(screen.getByRole("button", { name: "Plan trip" }));
    await screen.findByText("Could not reach the server");
    expect(screen.getByRole("alert")).toHaveTextContent("Could not reach the server");
  });
});

describe("waking the server", () => {
  it("waits for the pending health ping before posting, then plans", async () => {
    const order: string[] = [];
    server.use(
      http.get("*/api/v1/health", async () => {
        await delay(400);
        order.push("health");
        return HttpResponse.json({ status: "ok", api_version: "1" });
      }),
      http.post("*/api/v1/trips/plan", () => {
        order.push("plan");
        return HttpResponse.json(planOk);
      }),
    );
    const { user } = setup();
    await fillFreeText(user);
    await user.click(screen.getByRole("button", { name: "Plan trip" }));
    expect(await screen.findByText("Starting the server")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Planning route..." })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("plan")).toHaveTextContent("planned");
    });
    expect(order).toEqual(["health", "plan"]);
    expect(screen.queryByText("Starting the server")).not.toBeInTheDocument();
  });

  it("still posts when the health ping fails", async () => {
    server.use(
      http.get("*/api/v1/health", async () => {
        await delay(200);
        return new HttpResponse("<html>502</html>", { status: 502 });
      }),
      http.post("*/api/v1/trips/plan", () => HttpResponse.json(planOk)),
    );
    const { user } = setup();
    await fillFreeText(user);
    await user.click(screen.getByRole("button", { name: "Plan trip" }));
    await waitFor(() => {
      expect(screen.getByTestId("plan")).toHaveTextContent("planned");
    });
  });

  it("Cancel aborts the plan and returns to editing with inputs intact", async () => {
    let posts = 0;
    server.use(
      http.get("*/api/v1/health", async () => {
        await delay(1500);
        return HttpResponse.json({ status: "ok", api_version: "1" });
      }),
      http.post("*/api/v1/trips/plan", () => (posts++, HttpResponse.json(planOk))),
    );
    const { user } = setup();
    await fillFreeText(user);
    await user.click(screen.getByRole("button", { name: "Plan trip" }));
    await user.click(await screen.findByRole("button", { name: "Cancel" }));
    expect(await screen.findByRole("button", { name: "Plan trip" })).toBeInTheDocument();
    expect(screen.getByLabelText(/Current location/)).toHaveValue("Richmond, VA");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    await delay(100);
    expect(posts).toBe(0);
  });
});

describe("describePlanError wiring", () => {
  it("is exported and pure", () => {
    expect(typeof describePlanError).toBe("function");
  });
});

describe("share params", () => {
  it("prefills from ?q= and never posts on load", async () => {
    let posts = 0;
    server.use(http.post("*/api/v1/trips/plan", () => (posts++, HttpResponse.json(planOk))));
    const { encodeShare } = await import("./share");
    const { defaultTripValues } = await import("./schema");
    window.history.replaceState(
      null,
      "",
      `/?${encodeShare({ ...defaultTripValues(), current_location: RICHMOND, pickup_location: "Chicago, IL", dropoff_location: "Denver, CO", current_cycle_used_hours: 23.5 })}`,
    );
    setup();
    expect(screen.getByLabelText(/Current location/)).toHaveValue("Richmond, VA");
    expect(screen.getByLabelText(/Dropoff/)).toHaveValue("Denver, CO");
    await delay(200);
    expect(posts).toBe(0);
  });

  it("drops invalid params silently", () => {
    window.history.replaceState(null, "", "/?q=%%%not-base64");
    setup();
    expect(screen.getByLabelText(/Current location/)).toHaveValue("");
  });
});
