import { describe, expect, it } from "vitest";
import { parseSseBuffer } from "./jobSse";

describe("parseSseBuffer", () => {
  it("parses a complete JSON event", () => {
    const parsed = parseSseBuffer(
      'event: job.progress\ndata: {"event":"job.progress","progress":42}\n\n'
    );

    expect(parsed.messages).toEqual([
      {
        event: "job.progress",
        data: { event: "job.progress", progress: 42 },
      },
    ]);
    expect(parsed.remainder).toBe("");
  });

  it("retains incomplete events for the next stream chunk", () => {
    const parsed = parseSseBuffer(
      'event: job.progress\ndata: {"event":"job.progress"'
    );

    expect(parsed.messages).toEqual([]);
    expect(parsed.remainder).toContain("job.progress");
  });

  it("parses multiple events and windows line endings", () => {
    const parsed = parseSseBuffer(
      'event: job.heartbeat\r\ndata: {"event":"job.heartbeat"}\r\n\r\n' +
        'event: job.completed\r\ndata: {"event":"job.completed","progress":100}\r\n\r\n'
    );

    expect(parsed.messages).toHaveLength(2);
    expect(parsed.messages[1].event).toBe("job.completed");
  });

  it("keeps plain text data when JSON decoding is not possible", () => {
    const parsed = parseSseBuffer("data: still-valid-text\n\n");

    expect(parsed.messages[0]).toEqual({
      event: "message",
      data: "still-valid-text",
    });
  });
});

