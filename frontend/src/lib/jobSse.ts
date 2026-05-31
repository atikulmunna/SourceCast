export interface SseMessage<T = unknown> {
  event: string;
  data: T;
}

export interface JobStreamEvent {
  event: string;
  job_id: string;
  source_id?: string | null;
  status?: string;
  stage?: string | null;
  progress?: number;
  message?: string;
  current_step?: string | null;
  estimated_seconds_remaining?: number | null;
  error_code?: string;
  retryable?: boolean;
  updated_at?: string;
}

export function parseSseBuffer(buffer: string): {
  messages: SseMessage[];
  remainder: string;
} {
  const normalized = buffer.replaceAll("\r\n", "\n");
  const blocks = normalized.split("\n\n");
  const remainder = blocks.pop() || "";
  const messages = blocks.flatMap((block) => {
    let event = "message";
    const dataLines: string[] = [];

    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
    }

    if (!dataLines.length) return [];

    const rawData = dataLines.join("\n");
    try {
      return [{ event, data: JSON.parse(rawData) }];
    } catch {
      return [{ event, data: rawData }];
    }
  });

  return { messages, remainder };
}

export async function streamJobEvents(
  jobId: string,
  onEvent: (event: JobStreamEvent) => void,
  signal: AbortSignal
) {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const token =
    typeof window !== "undefined"
      ? window.__sourcecast_access_token
      : undefined;
  const response = await fetch(`${apiUrl}/api/v1/jobs/${jobId}/stream`, {
    credentials: "include",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(`Job stream failed with status ${response.status}`);
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
        onEvent(message.data as JobStreamEvent);
      }
    }

    if (done) break;
  }
}
