import { useEffect, useState } from "react";
import { listChatSessions } from "../api/api";
import type { ChatSession } from "../types";

type Props = {
  selectedSessionId: string | null;
  onSelectSession: (session: ChatSession) => void;
  refreshKey: number;
};

export default function SessionHistoryPanel({ selectedSessionId, onSelectSession, refreshKey }: Props) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);

  const fetchSessions = async () => {
    try {
      const res = await listChatSessions();
      setSessions(res.data.data.results || []);
    } catch (err) {
      console.error("Failed to load sessions:", err);
      setSessions([]);
    }
  };

  useEffect(() => {
    void fetchSessions();
  }, [refreshKey]);

  return (
    <div className="chat-session-list">
      <div className="chat-sidebar-header">
        <div className="panel-subtitle">Sessions</div>
        <button type="button" className="app-button app-button-ghost" onClick={fetchSessions}>RELOAD</button>
      </div>

      {sessions.length === 0 ? (
        <div className="empty-state compact">No sessions yet.</div>
      ) : (
        sessions.map((session) => (
          <button
            key={session.id}
            type="button"
            className={`chat-session-item ${selectedSessionId === session.id ? "active" : ""}`}
            onClick={() => onSelectSession(session)}
          >
            <div className="chat-session-item-title">{session.title || "Untitled session"}</div>
            <div className="chat-session-item-meta">
              <span>{session.status}</span>
              <span>{session.last_message_at || session.created_at}</span>
            </div>
          </button>
        ))
      )}
    </div>
  );
}
