import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { LandingPage } from "./LandingPage";

describe("LandingPage", () => {
  it("introduces MJD Square's buying and selling business and values", () => {
    render(
      <MemoryRouter>
        <LandingPage signedIn={false} />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("heading", { name: "A better way to buy. A better way to sell." }),
    ).toBeInTheDocument();
    expect(screen.getByText("GOOD GOODS. FAIR DEALS. BUILT ON TRUST.")).toBeInTheDocument();
    expect(screen.getByRole("img", {
      name: "Shelves stocked with assorted soft drinks, hot drinks, wine, and table water",
    })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Trust" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Quality goods" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Customer satisfaction" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Integrity" })).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Staff sign in" })).toHaveLength(3);
  });

  it("offers signed-in users a link to their workspace", () => {
    render(
      <MemoryRouter>
        <LandingPage signedIn />
      </MemoryRouter>,
    );

    expect(screen.getAllByRole("link", { name: "Open your workspace" })).toHaveLength(3);
  });
});
