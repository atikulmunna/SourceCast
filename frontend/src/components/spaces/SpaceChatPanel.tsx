"use client";

import { FormEvent, useState } from "react";
import { Clock, ExternalLink, Loader2, MessageSquare, Send } from "lucide-react";
import api from "@/lib/api";
import { streamChatTurn } from "@/lib/chatSse";
import { ChatMessage, ChatSession, getErrorMessage } from "@/lib/types";

interface SpaceChatPanelProps {
  spaceId: string;
  enabled: boolean;
}

export function SpaceChatPanel({ spaceId, enabled }: SpaceChatPanelProps) {
  const [session, setSession] = useState<ChatSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [streamedAnswer, setStreamedAnswer] = useState("");
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ask = async (event: FormEvent) => {
    event.preventDefault();
    const trimmedQuestion = question.trim();
    if (!enabled || asking || !trimmedQuestion) return;

    setAsking(true);
    setError(null);
    setStreamedAnswer("");
    try {
      let activeSession = session;
      if (!activeSession) {
        const { data } = await api.post<ChatSession>("/chat/sessions", {
          space_id: spaceId,
          title: trimmedQuestion.slice(0, 80),
        });
        activeSession = data;
        setSession(data);
      }

      setQuestion("");
      await streamChatTurn(activeSession.id, trimmedQuestion, (streamEvent) => {
        if (streamEvent.event === "chat.delta") {
          setStreamedAnswer(streamEvent.content);
        }
        if (streamEvent.event === "chat.completed") {
          setMessages((current) => [
            ...current,
            streamEvent.user_message,
            streamEvent.assistant_message,
          ]);
          setStreamedAnswer("");
        }
      });
    } catch (err) {
      setError(getErrorMessage(err) === "An unexpected error occurred" && err instanceof Error
        ? err.message
        : getErrorMessage(err));
    } finally {
      setAsking(false);
    }
  };

  return (
    <section className="mt-8 border-t pt-8" style={{ borderColor: "var(--border)" }}>
      <div className="flex items-center gap-2 mb-4">
        <MessageSquare size={17} style={{ color: "#2dd4bf" }} />
        <h2 className="text-sm font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
          Research Chat
        </h2>
      </div>

      <div className="rounded-lg overflow-hidden" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
        <div className="min-h-48 max-h-[520px] overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && !streamedAnswer ? (
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>
              {enabled
                ? "Ask a question across the indexed sources in this space."
                : "Add and index a source before starting a research chat."}
            </p>
          ) : (
            messages.map((message) => <ChatBubble key={message.id} message={message} />)
          )}
          {streamedAnswer && (
            <div className="max-w-3xl">
              <p className="text-sm leading-relaxed">{streamedAnswer}</p>
            </div>
          )}
          {asking && !streamedAnswer && (
            <div className="flex items-center gap-2 text-sm" style={{ color: "var(--text-muted)" }}>
              <Loader2 size={15} className="animate-spin" />
              Searching indexed evidence
            </div>
          )}
        </div>

        <form onSubmit={ask} className="flex gap-2 p-3 border-t" style={{ borderColor: "var(--border)" }}>
          <input
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            disabled={!enabled || asking}
            placeholder={enabled ? "Ask across this space..." : "Index a source to start chatting"}
            className="min-w-0 flex-1 rounded-lg px-3 py-2 text-sm outline-none disabled:opacity-50"
            style={{
              background: "var(--bg-secondary)",
              border: "1px solid var(--border)",
              color: "var(--text-primary)",
            }}
          />
          <button
            type="submit"
            disabled={!enabled || asking || !question.trim()}
            title="Send question"
            className="w-10 h-10 rounded-lg flex items-center justify-center disabled:opacity-40"
            style={{ background: "#0d9488", color: "#fff" }}
          >
            {asking ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
          </button>
        </form>
      </div>

      {error && <p className="text-sm mt-3" style={{ color: "#f87171" }}>{error}</p>}
    </section>
  );
}

function ChatBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={isUser ? "flex justify-end" : "max-w-3xl"}>
      <div
        className={isUser ? "rounded-lg px-3 py-2 max-w-xl" : ""}
        style={isUser ? { background: "rgba(13,148,136,0.14)" } : undefined}
      >
        <p className="text-sm leading-relaxed">{message.content}</p>
        {message.evidence.length > 0 && (
          <div className="mt-3 grid gap-2">
            {message.evidence.map((item) => (
              <div
                key={item.id}
                className="rounded-lg p-3"
                style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)" }}
              >
                <div className="flex items-center justify-between gap-2 mb-1 text-xs">
                  <span className="flex items-center gap-2" style={{ color: "#2dd4bf" }}>
                    <span className="flex items-center gap-1">
                      <Clock size={12} />
                      {formatTimestamp(Number(item.start_time_sec))} - {formatTimestamp(Number(item.end_time_sec))}
                    </span>
                    {item.navigation_url && (
                      <a
                        href={item.navigation_url}
                        target="_blank"
                        rel="noreferrer"
                        title="Open source at timestamp"
                        className="hover:opacity-80"
                      >
                        <ExternalLink size={12} />
                      </a>
                    )}
                  </span>
                  <span style={{ color: "var(--text-muted)" }}>{item.confidence_label}</span>
                </div>
                {item.source_title && <p className="text-xs font-medium mb-1">{item.source_title}</p>}
                <p className="text-xs leading-relaxed" style={{ color: "var(--text-secondary)" }}>{item.excerpt}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function formatTimestamp(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = Math.floor(totalSeconds % 60);
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}
