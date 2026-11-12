import { refreshAccessToken } from "./api";
import { apiPath } from "./apiBase";
import { parseSseBuffer } from "./sse";
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

function postQuestion(sessionId: string, question: string, signal?: AbortSignal) {
  const token =
    typeof window !== "undefined"
      ? window.__sourcecast_access_token
      : undefined;
  return fetch(apiPath(`/api/v1/chat/sessions/${sessionId}/ask`), {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ question }),
    signal,
  });
}

export async function streamChatTurn(
  sessionId: string,
  question: string,
  onEvent: (event: ChatStreamEvent) => void,
  signal?: AbortSignal
) {
  let response = await postQuestion(sessionId, question, signal);

  // fetch bypasses the axios interceptor, so refresh an expired access token
  // here. Retrying is safe: a 401 is rejected before the question is saved.
  if (response.status === 401) {
    await refreshAccessToken();
    response = await postQuestion(sessionId, question, signal);
  }

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
