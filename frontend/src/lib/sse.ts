export interface SseMessage<T = unknown> {
  event: string;
  data: T;
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
