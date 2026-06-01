import { parseSseBuffer } from "./jobSse";
import { ChatMessage } from "./types";

export interface ChatStartedEvent {
  event: "chat.started";
  session_id: string;
}

export interface ChatDeltaEvent {
  event: "chat.delta";
  session_id: string;
  content: string;
}

export interface ChatCompletedEvent {
  event: "chat.completed";
  session_id: string;
  user_message: ChatMessage;
  assistant_message: ChatMessage;
  insufficient_evidence: boolean;
}

export type ChatStreamEvent =
  | ChatStartedEvent
  | ChatDeltaEvent
  | ChatCompletedEvent;

export async function streamChatTurn(
  sessionId: string,
  question: string,
  onEvent: (event: ChatStreamEvent) => void,
  signal?: AbortSignal
) {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const token =
    typeof window !== "undefined"
      ? window.__sourcecast_access_token
      : undefined;
  const response = await fetch(`${apiUrl}/api/v1/chat/sessions/${sessionId}/ask`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ question }),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(`Chat stream failed with status ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const parsed = parseSseBuffer(buffer);
    buffer = parsed.remainder;

    for (const message of parsed.messages) {
      if (typeof message.data === "object" && message.data !== null) {
        onEvent(message.data as ChatStreamEvent);
      }
    }

    if (done) break;
  }
}
