import { describe, expect, it } from "vitest";
import { afterEach, vi } from "vitest";
import { api, ApiError, readCsrfToken } from "./api";

describe("readCsrfToken", () => {
  it("finds the CSRF cookie among other cookies", () => {
    expect(readCsrfToken("theme=light; mjd_csrf=abc123; session=ignored")).toBe("abc123");
  });

  describe("session verification errors", () => {
    afterEach(() => vi.unstubAllGlobals());

    it("treats an unauthorized response as a signed-out session", async () => {
      vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 401 })));

      await expect(api.currentUser()).resolves.toBeNull();
    });

    it("explains a plain-text proxy or API failure", async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(new Response("proxy error", { status: 500 })),
      );

      await expect(api.currentUser()).rejects.toMatchObject({
        message: "The API server returned HTTP 500. Check that the backend and database are running.",
        status: 500,
      } satisfies Partial<ApiError>);
    });
  });

  it("decodes the CSRF cookie value", () => {
    expect(readCsrfToken("mjd_csrf=hello%2Fworld")).toBe("hello/world");
  });

  it("returns null if the cookie is absent", () => {
    expect(readCsrfToken("theme=light")).toBeNull();
  });
});

describe("password recovery API", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe("sign-in API", () => {
    afterEach(() => {
      vi.unstubAllGlobals();
    });

    it("uses a phone number as the sign-in identifier when no email is provided", async () => {
      const fetchMock = vi.fn().mockResolvedValue(
        Response.json({ id: "owner-id", email: null, phone: "+2348031234567" }),
      );
      vi.stubGlobal("fetch", fetchMock);

      await api.login("+2348031234567", "a strong owner password");

      const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
      expect(JSON.parse(options.body as string)).toEqual({
        phone: "+2348031234567",
        password: "a strong owner password",
      });
    });
  });

  it("requests a password reset without requiring a CSRF cookie", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      Response.json({
        message: "If an eligible account exists, password reset instructions will be sent.",
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.requestPasswordReset("user@example.com")).resolves.toMatchObject({
      message: expect.any(String),
    });

    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(options.headers).not.toHaveProperty("X-CSRF-Token");
    expect(JSON.parse(options.body as string)).toEqual({
      email: "user@example.com",
    });
  });

  it("resets a password without requiring a CSRF cookie", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      Response.json({ message: "Password reset successfully." }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      api.resetPassword("a-valid-reset-token", "new-secure-password"),
    ).resolves.toMatchObject({ message: expect.any(String) });

    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(options.headers).not.toHaveProperty("X-CSRF-Token");
    expect(JSON.parse(options.body as string)).toEqual({
      token: "a-valid-reset-token",
      new_password: "new-secure-password",
    });
  });
});
