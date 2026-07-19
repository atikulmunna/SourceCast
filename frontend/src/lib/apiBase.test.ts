import { afterEach, describe, expect, it, vi } from "vitest";
import { apiPath, getApiOrigin } from "./apiBase";

const originalApiUrl = process.env.NEXT_PUBLIC_API_URL;
const originalNodeEnv = process.env.NODE_ENV;

afterEach(() => {
  if (originalApiUrl === undefined) {
    delete process.env.NEXT_PUBLIC_API_URL;
  } else {
    process.env.NEXT_PUBLIC_API_URL = originalApiUrl;
  }
  process.env.NODE_ENV = originalNodeEnv;
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
    delete process.env.NEXT_PUBLIC_API_URL;
    process.env.NODE_ENV = "development";

    expect(getApiOrigin()).toBe("http://localhost:8000");
  });
});
