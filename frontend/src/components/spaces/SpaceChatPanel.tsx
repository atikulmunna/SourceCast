"use client";

import { FormEvent, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Clock, ExternalLink, Loader2, MessageSquare, Plus, Send, Trash2 } from "lucide-react";
import api from "@/lib/api";
import { streamChatTurn } from "@/lib/chatSse";
import { ChatMessage, ChatSession, getErrorMessage } from "@/lib/types";
import { SaveInsightButton } from "@/components/insights/SaveInsightButton";

interface SpaceChatPanelProps {
  spaceId: string;
  enabled: boolean;
}

export function SpaceChatPanel({ spaceId, enabled }: SpaceChatPanelProps) {
  const queryClient = useQueryClient();
  const [session, setSession] = useState<ChatSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [streamedAnswer, setStreamedAnswer] = useState("");
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: sessions = [], isLoading: sessionsLoading } = useQuery<ChatSession[]>({
    queryKey: ["chatSessions", spaceId],
    queryFn: async () => {
      const { data } = await api.get<ChatSession[]>("/chat/sessions", {
        params: { space_id: spaceId },
      });
      return data;
    },
  });

  const { data: persistedMessages = [], isLoading: messagesLoading } = useQuery<ChatMessage[]>({
    queryKey: ["chatMessages", session?.id],
    queryFn: async () => {
      const { data } = await api.get<ChatMessage[]>(`/chat/sessions/${session?.id}/messages`);
      return data;
    },
    enabled: Boolean(session?.id),
  });

  const visibleMessages = session && !asking ? persistedMessages : messages;

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
        await queryClient.invalidateQueries({ queryKey: ["chatSessions", spaceId] });
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
      await queryClient.invalidateQueries({ queryKey: ["chatSessions", spaceId] });
      await queryClient.invalidateQueries({ queryKey: ["chatMessages", activeSession.id] });
    } catch (err) {
      setError(getErrorMessage(err) === "An unexpected error occurred" && err instanceof Error
        ? err.message
        : getErrorMessage(err));
    } finally {
      setAsking(false);
    }
  };

  const startNewChat = () => {
    setSession(null);
    setMessages([]);
    setStreamedAnswer("");
    setError(null);
  };

  const resumeSession = (nextSession: ChatSession) => {
    setSession(nextSession);
    setStreamedAnswer("");
    setError(null);
  };

  const deleteSession = async (sessionId: string) => {
    await api.delete(`/chat/sessions/${sessionId}`);
    if (session?.id === sessionId) {
      startNewChat();
    }
    await queryClient.invalidateQueries({ queryKey: ["chatSessions", spaceId] });
  };

  return (
    <section className="mt-8 border-t pt-8" style={{ borderColor: "var(--border)" }}>
      <div className="flex items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-2">
          <MessageSquare size={17} style={{ color: "#2dd4bf" }} />
          <h2 className="text-sm font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
            Research Chat
          </h2>
        </div>
        <button
          type="button"
          onClick={startNewChat}
          title="Start new chat"
          className="w-8 h-8 rounded-lg flex items-center justify-center hover:opacity-80"
          style={{ border: "1px solid var(--border)", color: "#2dd4bf" }}
        >
          <Plus size={15} />
        </button>
      </div>

      <div className="grid gap-4 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="rounded-lg p-3" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
          {sessionsLoading ? (
            <Loader2 size={16} className="animate-spin" style={{ color: "#2dd4bf" }} />
          ) : sessions.length === 0 ? (
            <p className="text-sm" style={{ color: "var(--text-muted)" }}>No saved chats yet.</p>
          ) : (
            <div className="space-y-2">
              {sessions.map((item) => (
                <div
                  key={item.id}
                  className="rounded-lg p-2"
                  style={{
                    background: item.id === session?.id ? "rgba(13,148,136,0.12)" : "var(--bg-secondary)",
                    border: "1px solid var(--border)",
                  }}
                >
                  <div className="flex items-start justify-between gap-2">
                    <button
                      type="button"
                      onClick={() => resumeSession(item)}
                      className="min-w-0 text-left text-sm font-medium hover:opacity-80"
                    >
                      <span className="block truncate">{item.title}</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => deleteSession(item.id)}
                      title="Delete chat"
                      className="w-7 h-7 shrink-0 rounded-lg flex items-center justify-center hover:opacity-80"
                      style={{ color: "#f87171", border: "1px solid var(--border)" }}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                  <p className="mt-1 text-[11px]" style={{ color: "var(--text-muted)" }}>
                    {formatDate(item.updated_at)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </aside>

        <div className="rounded-lg overflow-hidden" style={{ background: "var(--bg-card)", border: "1px solid var(--border)" }}>
          <div className="min-h-48 max-h-[520px] overflow-y-auto p-4 space-y-4">
            {messagesLoading && session ? (
              <div className="flex items-center gap-2 text-sm" style={{ color: "var(--text-muted)" }}>
                <Loader2 size={15} className="animate-spin" />
                Loading chat history
              </div>
            ) : visibleMessages.length === 0 && !streamedAnswer ? (
              <p className="text-sm" style={{ color: "var(--text-muted)" }}>
                {enabled
                  ? "Ask a question across the indexed sources in this space."
                  : "Add and index a source before starting a research chat."}
              </p>
            ) : (
              visibleMessages.map((message) => <ChatBubble key={message.id} message={message} spaceId={spaceId} />)
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
      </div>

      {error && <p className="text-sm mt-3" style={{ color: "#f87171" }}>{error}</p>}
    </section>
  );
}

function ChatBubble({ message, spaceId }: { message: ChatMessage; spaceId: string }) {
  const isUser = message.role === "user";
  return (
    <div className={isUser ? "flex justify-end" : "max-w-3xl"}>
      <div
        className={isUser ? "rounded-lg px-3 py-2 max-w-xl" : ""}
        style={isUser ? { background: "rgba(13,148,136,0.14)" } : undefined}
      >
        <div className="flex items-start gap-2">
          <p className="text-sm leading-relaxed flex-1">{message.content}</p>
          {!isUser && <SaveInsightButton spaceId={spaceId} content={message.content} title="Chat answer" />}
        </div>
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
                <div className="flex items-start gap-2">
                  <p className="text-xs leading-relaxed flex-1" style={{ color: "var(--text-secondary)" }}>{item.excerpt}</p>
                  <SaveInsightButton
                    spaceId={spaceId}
                    content={item.excerpt}
                    title={item.source_title}
                    sourceId={item.source_id}
                    evidenceItemId={item.id}
                  />
                </div>
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

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}
