import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import IncidentDashboard from "./IncidentDashboard";

const FIXTURE_URL = "/incidents/demo-001?fixture=1";

beforeEach(() => {
  window.history.replaceState({}, "", FIXTURE_URL);
});

describe("IncidentDashboard (fixture mode)", () => {
  it("shows the mock banner, both statements, and the report panel", async () => {
    render(<IncidentDashboard incidentId="demo-001" />);

    expect(await screen.findByTestId("mock-banner")).toHaveTextContent("Demo / Mock");
    expect(screen.getByTestId("fixture-chip")).toHaveTextContent("Fixture mode");
    expect(screen.getByTestId("statement-statement-a")).toBeInTheDocument();
    expect(screen.getByTestId("statement-statement-b")).toBeInTheDocument();
    expect(screen.getByTestId("report-panel")).toHaveTextContent("Human review: required");
    expect(screen.getByTestId("report-panel")).toHaveTextContent(
      "No legal fault determination is provided",
    );
  });

  it("selects a claim, shows its evidence, and seeks the player to the window start", async () => {
    const user = userEvent.setup();
    render(<IncidentDashboard incidentId="demo-001" />);
    const contradictedRow = await screen.findByTestId("claim-row-c4");

    await user.click(contradictedRow);

    expect(contradictedRow).toHaveAttribute("aria-pressed", "true");
    const panel = screen.getByTestId("evidence-panel");
    expect(panel).toHaveTextContent("I stayed in my lane.");
    expect(panel).toHaveTextContent("Synthetic fixture assigns contradicted");
    expect(panel).toHaveTextContent("0:08.0 – 0:12.0");
    expect(screen.getByTestId("video-time-readout")).toHaveTextContent("0:08.0");
    expect(screen.getByTestId("video-player")).toHaveAttribute("data-current-time", "8.0");
  });

  it("keeps not-visible claims distinct and shows their reviewed window", async () => {
    const user = userEvent.setup();
    render(<IncidentDashboard incidentId="demo-001" />);
    const row = await screen.findByTestId("claim-row-c3");

    await user.click(row);

    const panel = screen.getByTestId("evidence-panel");
    expect(within(panel).getByRole("status")).toHaveTextContent("Not visible");
    expect(panel).toHaveTextContent("Signal is unseen; absence cannot contradict the claim.");
    expect(panel).toHaveTextContent("Synthetic review window; signal outside frame.");
  });

  it("selects claims from timeline markers and separates detector observations", async () => {
    const user = userEvent.setup();
    render(<IncidentDashboard incidentId="demo-001" />);
    const marker = await screen.findByTestId("timeline-marker-c1");

    await user.click(marker);

    expect(screen.getByTestId("claim-row-c1")).toHaveAttribute("aria-pressed", "true");
    const panel = screen.getByTestId("evidence-panel");
    expect(panel).toHaveTextContent("Model evidence (1)");
    expect(panel).toHaveTextContent("Detector observations — YOLO cross-check (1)");
    expect(panel).toHaveTextContent("scripted_lane_change");
    expect(panel).toHaveTextContent("not independent corroboration");
  });
});
