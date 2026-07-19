import { afterEach, describe, expect, it, vi } from "vitest";
import { streamChatTurn } from "./chatSse";

function streamResponse(chunks: string[]) {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream({
      start(controller) {
        chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
        controller.close();
      },
    }),
    { status: 200 }
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("streamChatTurn", () => {
  it("posts the question and emits decoded chat events across chunks", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      streamResponse([
        'event: chat.started\ndata: {"event":"chat.started","session_id":"session-1"}\n\n',
        'event: chat.delta\ndata: {"event":"chat.delta","session_id":"session-1",',
        '"content":"Grounded answer."}\n\n',
        'event: chat.completed\ndata: {"event":"chat.completed","session_id":"session-1",',
        '"user_message":{},"assistant_message":{},"insufficient_evidence":false}\n\n',
      ])
    );
    vi.stubGlobal("fetch", fetchMock);
    const events: unknown[] = [];

    await streamChatTurn("session-1", "What happened?", (event) => events.push(event));

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/chat/sessions/session-1/ask",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ question: "What happened?" }),
      })
    );
    expect(events).toHaveLength(3);
    expect(events[1]).toEqual({
      event: "chat.delta",
      session_id: "session-1",
      content: "Grounded answer.",
    });
  });

  it("reports a failed stream response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 503 })));

    await expect(streamChatTurn("session-1", "Question?", () => undefined)).rejects.toThrow(
      "Chat stream failed with status 503"
    );
  });
});
