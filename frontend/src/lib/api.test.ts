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
