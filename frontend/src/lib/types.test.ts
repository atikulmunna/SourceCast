import { describe, expect, it } from "vitest";
import { getErrorMessage } from "./types";

describe("getErrorMessage", () => {
  it("uses FastAPI detail strings", () => {
    expect(
      getErrorMessage({ response: { data: { detail: "Could not preview source" } } }),
    ).toBe("Could not preview source");
  });

  it("formats FastAPI validation errors", () => {
    expect(
      getErrorMessage({
        response: { data: { detail: [{ msg: "URL is required", type: "missing" }] } },
      }),
    ).toBe("URL is required");
  });

  it("reports server errors when no response body is available", () => {
    expect(getErrorMessage({ response: { status: 500 } })).toBe(
      "The server hit an error while processing this request.",
    );
  });

  it("explains network failures without a response", () => {
    expect(getErrorMessage({ message: "Network Error" })).toContain(
      "Could not reach the backend",
    );
  });

  it("explains request timeouts without a response", () => {
    expect(getErrorMessage({ code: "ECONNABORTED" })).toContain(
      "too long to respond",
    );
  });
});
