import { afterEach, describe, expect, it, vi } from "vitest";
import { apiPath, getApiOrigin } from "./apiBase";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("api base helpers", () => {
  it("uses an explicit configured API origin", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.example.com/");

    expect(getApiOrigin()).toBe("https://api.example.com");
    expect(apiPath("/api/v1/auth/login")).toBe("https://api.example.com/api/v1/auth/login");
  });

  it("keeps production same-origin when API origin is intentionally empty", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "");

    expect(getApiOrigin()).toBe("");
    expect(apiPath("/api/v1/auth/login")).toBe("/api/v1/auth/login");
  });

  it("falls back to localhost only for local development", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", undefined);
    vi.stubEnv("NODE_ENV", "development");

    expect(getApiOrigin()).toBe("http://localhost:8000");
  });
});
