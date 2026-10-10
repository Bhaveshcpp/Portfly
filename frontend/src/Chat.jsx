import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";

const storeKey = (id) => `portfly:conversation:${id}`;
const KEY_HEADER = "X-Conversation-Key";

// A saved thread is {id, key}: the server only lets you read or continue a conversation if you hold its key.
const remember = (id, thread) => {
  try {
    if (!thread) localStorage.removeItem(storeKey(id));
    else localStorage.setItem(storeKey(id), JSON.stringify(thread));
  } catch {
    /* storage can be unavailable (private mode); the chat still works, it just won't survive a refresh */
  }
};
const recall = (id) => {
  try {
    const raw = localStorage.getItem(storeKey(id));
    if (!raw) return null;
    const thread = JSON.parse(raw);
    if (thread && Number.isInteger(thread.id) && typeof thread.key === "string" && thread.key) return thread;
    localStorage.removeItem(storeKey(id)); // older format (id only): unusable without a key, so drop it
  } catch {
    /* unreadable value: treat as no saved thread */
  }
  return null;
};

export default function Chat() {
  const [users, setUsers] = useState([]);
  const [userId, setUserId] = useState("");
  const [conversationId, setConversationId] = useState(null);
  const [conversationKey, setConversationKey] = useState(null);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [latency, setLatency] = useState(null);
  const bottom = useRef(null);

  useEffect(() => {
    api("/api/users").then((rows) => {
      setUsers(rows);
      if (rows[0]) pickUser(rows[0].user_id);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  // Reopen this user's last thread after a refresh instead of starting from scratch.
  async function pickUser(id) {
    setUserId(id);
    setConversationId(null);
    setConversationKey(null);
    setMessages([]);
    setLatency(null);
    const saved = recall(id);
    if (!saved) return;
    try {
      const convo = await api(`/api/users/${id}/conversations/${saved.id}/messages`, {
        headers: { [KEY_HEADER]: saved.key },
      });
      if (convo.user_id !== id) throw new Error("thread belongs to someone else");
      setConversationId(convo.conversation_id);
      setConversationKey(saved.key);
      setMessages(convo.messages.map(({ role, content }) => ({ role, content })));
    } catch {
      remember(id, null);
    }
  }

  function newChat() {
    remember(userId, null);
    setConversationId(null);
    setConversationKey(null);
    setMessages([]);
    setLatency(null);
  }

  async function send(event) {
    event.preventDefault();
    if (!draft.trim() || !userId || busy) return;
    const text = draft.trim();
    setDraft("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    setBusy(true);
    try {
      const result = await api("/api/chat", {
        method: "POST",
        headers: conversationId && conversationKey ? { [KEY_HEADER]: conversationKey } : {},
        body: JSON.stringify({
          user_id: userId,
          conversation_id: conversationId,
          message: text,
        }),
      });
      setConversationId(result.conversation_id);
      if (result.conversation_key) {
        // sent once, when the conversation is created; keep it next to the id so a refresh can resume
        setConversationKey(result.conversation_key);
        remember(userId, { id: result.conversation_id, key: result.conversation_key });
      }
      setMessages((m) => [...m, { role: "assistant", content: result.reply }]);
      setLatency(result.total_ms);
    } catch (err) {
      if (err.status === 401 || err.status === 403) {
        // the saved key no longer opens this conversation: start fresh instead of failing forever
        remember(userId, null);
        setConversationId(null);
        setConversationKey(null);
        setMessages((m) => [
          ...m,
          { role: "assistant", content: "That conversation is no longer available, so your message was not sent. Send it again to start a new chat." },
        ]);
        return;
      }
      setMessages((m) => [
        ...m,
        { role: "assistant", content: `Could not reach Portfly: ${err.message}` },
      ]);
    } finally {
      setBusy(false);
    }
  }

  const user = users.find((u) => u.user_id === userId);

  return (
    <div className="wa">
      <aside className="sidebar">
        <header>
          <div>Portfly</div>
          <small>WhatsApp simulation</small>
        </header>
        <div className="user-list">
          {users.map((u) => (
            <div
              key={u.user_id}
              className={`user-row ${u.user_id === userId ? "active" : ""}`}
              onClick={() => pickUser(u.user_id)}
            >
              <div className="avatar">{u.name[0]}</div>
              <div>
                <div>{u.name}</div>
                <small>
                  {u.city} · {u.property_count} properties
                </small>
              </div>
            </div>
          ))}
        </div>
      </aside>
      <section className="chat">
        <div className="chat-header">
          <div className="avatar">{user?.name?.[0] || "?"}</div>
          <div>
            <div>{user?.name || "Select a client"}</div>
            <small>
              {user?.preferences}
              {latency != null ? ` · last reply ${Math.round(latency)} ms` : ""}
            </small>
          </div>
          <button type="button" onClick={newChat} style={{ marginLeft: "auto" }}>New chat</button>
        </div>
        <div className="thread">
          {messages.length === 0 && (
            <div className="bubble assistant">
              Hi {user?.name || "there"}. Ask me about your portfolio — totals, retail vs office, a
              property in Mumbai, a what-if, or add/update a holding.
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`bubble ${m.role}`}>
              {m.content}
            </div>
          ))}
          {busy && <div className="bubble assistant">Portfly is looking at the books…</div>}
          <div ref={bottom} />
        </div>
        <form className="composer" onSubmit={send}>
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Type a message"
          />
          <button type="submit">Send</button>
        </form>
      </section>
    </div>
  );
}
