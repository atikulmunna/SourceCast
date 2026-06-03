import { afterEach, describe, expect, it, vi } from "vitest";
import { notifySessionExpired, setSessionExpiredHandler } from "./api";

afterEach(() => {
  setSessionExpiredHandler(null);
  vi.unstubAllGlobals();
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
