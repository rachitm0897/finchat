import { useEffect, useState } from "react";
import { createChatSession, getChatMessages, sendChatMessage } from "../api/api";
import type { ChatMessage, ChatSession } from "../types";
import SessionHistoryPanel from "./SessionHistoryPanel";

type Props = {
  ticker: string;
};

export default function ChatPanel({ ticker }: Props) {
  const [session, setSession] = useState<ChatSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionREFRESHKey, setSessionREFRESHKey] = useState(0);

  const loadSessionMessages = async (sessionId: string) => {
    try {
      const res = await getChatMessages(sessionId);
      const rows = res.data.data.results || [];
      const mapped: ChatMessage[] = rows
        .filter((row: any) => row.role === "user" || row.role === "assistant")
        .map((row: any) => ({
          id: row.id,
          role: row.role,
          content: row.content,
          created_at: row.created_at,
        }));
      setMessages(mapped);
    } catch (err) {
      console.error("Failed to refresh messages:", err);
      setMessages([]);
    }
  };

  const startNewSession = async () => {
    try {
      const res = await createChatSession(`${ticker} research`, { initial_ticker: ticker });
      const created = res.data.data.session as ChatSession;
      setSession(created);
      setMessages([]);
      setSessionREFRESHKey((prev) => prev + 1);
    } catch (err) {
      console.error("Failed to create chat session:", err);
    }
  };

  useEffect(() => {
    setSession(null);
    setMessages([]);
  }, [ticker]);

  const ensureSession = async () => {
    if (session) return session;
    const res = await createChatSession(`${ticker} research`, { initial_ticker: ticker });
    const created = res.data.data.session as ChatSession;
    setSession(created);
    setSessionREFRESHKey((prev) => prev + 1);
    return created;
  };

  const handleSEND = async () => {
    if (!input.trim()) return;
    setLoading(true);
    try {
      const currentSession = await ensureSession();
      await sendChatMessage(currentSession.id, input);
      setInput("");
      await loadSessionMessages(currentSession.id);
      setSessionREFRESHKey((prev) => prev + 1);
    } catch (err: any) {
      console.error("Chat failed:", err);
      const message = err.response?.data ? JSON.stringify(err.response.data, null, 2) : err.message || "Unknown chat error";
      setMessages((prev) => [...prev, { role: "assistant", content: `Error: ${message}` }]);
    }
    setLoading(false);
  };

  const handleSelectSession = async (selected: ChatSession) => {
    setSession(selected);
    await loadSessionMessages(selected.id);
  };

  return (
    <section className="panel chat-panel-shell terminal-grid-bg">
      <div className="panel-header">
        <div>
          <h3>Chat Workspace</h3>
          <div className="panel-subtitle">Compact assistant pane for follow-up analysis on {ticker}</div>
        </div>
        <button type="button" className="app-button app-button-ghost" onClick={startNewSession}>NEW SESSION</button>
      </div>

      <div className="chat-shell-grid">
        <aside className="chat-shell-sidebar">
          <SessionHistoryPanel
            selectedSessionId={session?.id || null}
            onSelectSession={handleSelectSession}
            refreshKey={sessionREFRESHKey}
          />
        </aside>

        <div className="chat-shell-main">
          <div className="chat-meta-bar">
            <span>Session: {session?.id || "not started"}</span>
            <span>Status: {session?.status || "idle"}</span>
          </div>

          <div className="chat-transcript">
            {messages.length === 0 ? (
              <div className="empty-state">No chat messages yet.</div>
            ) : (
              messages.map((msg, idx) => (
                <div key={msg.id || idx} className={`transcript-row ${msg.role}`}>
                  <div className="transcript-role">{msg.role}</div>
                  <div className="transcript-content">{msg.content}</div>
                </div>
              ))
            )}
          </div>

          <div className="chat-entry-row">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={`Ask about ${ticker}. Keep it focused, unlike most meetings.`}
              rows={4}
            />
            <div className="chat-entry-actions">
              <button type="button" className="app-button" onClick={handleSEND} disabled={loading}>
                {loading ? "SENDing" : "SEND"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
