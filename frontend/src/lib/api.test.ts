import { afterEach, describe, expect, it, vi } from "vitest";
import api, { notifySessionExpired, refreshAccessToken, setSessionExpiredHandler } from "./api";

afterEach(() => {
  setSessionExpiredHandler(null);
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("notifySessionExpired", () => {
  it("clears the in-memory access token and notifies the auth store handler", () => {
    const handler = vi.fn();
    const windowMock = {
      __sourcecast_access_token: "token",
      location: { pathname: "/app", href: "http://localhost:3000/app" },
    };
    vi.stubGlobal("window", windowMock);
    setSessionExpiredHandler(handler);

    notifySessionExpired();

    expect(windowMock.__sourcecast_access_token).toBeUndefined();
    expect(handler).toHaveBeenCalledOnce();
    expect(windowMock.location.href).toBe("http://localhost:3000/app");
  });

  it("falls back to the login route when no handler is registered", () => {
    const windowMock = {
      __sourcecast_access_token: "token",
      location: { pathname: "/app", href: "http://localhost:3000/app" },
    };
    vi.stubGlobal("window", windowMock);

    notifySessionExpired();

    expect(windowMock.__sourcecast_access_token).toBeUndefined();
    expect(windowMock.location.href).toBe("/login");
  });
});

describe("refreshAccessToken", () => {
  it("shares one refresh request between concurrent callers", async () => {
    const windowMock: { __sourcecast_access_token?: string } = {};
    vi.stubGlobal("window", windowMock);
    const post = vi.spyOn(api, "post").mockResolvedValue({ data: { access_token: "fresh-token" } });

    const tokens = await Promise.all([refreshAccessToken(), refreshAccessToken()]);

    expect(post).toHaveBeenCalledOnce();
    expect(post).toHaveBeenCalledWith("/auth/refresh");
    expect(tokens).toEqual(["fresh-token", "fresh-token"]);
    expect(windowMock.__sourcecast_access_token).toBe("fresh-token");
  });

  it("reports the expired session once when the refresh fails", async () => {
    vi.stubGlobal("window", {
      __sourcecast_access_token: "expired-token",
      location: { pathname: "/app", href: "http://localhost:3000/app" },
    });
    const handler = vi.fn();
    setSessionExpiredHandler(handler);
    vi.spyOn(api, "post").mockRejectedValue(new Error("refresh rejected"));

    const results = await Promise.allSettled([refreshAccessToken(), refreshAccessToken()]);

    expect(results.map((result) => result.status)).toEqual(["rejected", "rejected"]);
    expect(handler).toHaveBeenCalledOnce();
  });
});
