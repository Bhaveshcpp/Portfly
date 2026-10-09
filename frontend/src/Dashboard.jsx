import { useEffect, useState } from "react";
import { api } from "./api.js";

export default function Dashboard() {
  const [overview, setOverview] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [users, setUsers] = useState([]);
  const [active, setActive] = useState(null);
  const [onlyFlagged, setOnlyFlagged] = useState(false);

  async function refresh() {
    const [dash, convos, people] = await Promise.all([
      api("/api/dashboard"),
      api("/api/conversations"),
      api("/api/users"),
    ]);
    setOverview(dash);
    setConversations(convos);
    setUsers(people);
  }

  async function resolve(id) {
    await api(`/api/conversations/${id}/resolve`, { method: "POST" });
    await refresh();
    setActive(await api(`/api/conversations/${id}`));
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 8000);
    return () => clearInterval(id);
  }, []);

  async function openConvo(id) {
    setActive(await api(`/api/conversations/${id}`));
  }

  if (!overview) return <div className="dash">Loading desk…</div>;

  return (
    <div className="dash">
      <h2>Business desk</h2>
      <p>Observation only — users, threads, tool activity, flags, and latency.</p>
      <div className="cards">
        <div className="card">
          <span>Users</span>
          <strong>{overview.users}</strong>
        </div>
        <div className="card">
          <span>Properties</span>
          <strong>{overview.properties}</strong>
        </div>
        <div className="card">
          <span>Conversations</span>
          <strong>{overview.conversations}</strong>
        </div>
        <div className="card">
          <span>Needs attention</span>
          <strong className={overview.attention_count ? "flag" : ""}>
            {overview.attention_count}
          </strong>
        </div>
      </div>
      <p>
        Reply time (last {overview.recent_runs.length} runs): p50 <b>{Math.round(overview.p50_total_ms)} ms</b>
        {" · "}p95 <b>{Math.round(overview.p95_total_ms)} ms</b>
        {" · "}avg model <b>{Math.round(overview.avg_model_ms)} ms</b>
        {" · "}avg tools <b>{Math.round(overview.avg_tool_ms)} ms</b>
        {" · "}errors <b className={overview.error_runs ? "flag" : ""}>{overview.error_runs}</b>
        {" · "}fallback runs <b>{overview.fallback_runs}</b>
        {" · "}tokens in/out <b>{overview.prompt_tokens}/{overview.completion_tokens}</b>
      </p>

      <h3>Users</h3>
      <table>
        <thead>
          <tr>
            <th>User</th>
            <th>City</th>
            <th>Properties</th>
            <th>Conversations</th>
            <th>Needs attention</th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.user_id}>
              <td>{u.name} ({u.user_id})</td>
              <td>{u.city}</td>
              <td>{u.property_count}</td>
              <td>{u.conversation_count}</td>
              <td className={u.attention_count ? "flag" : ""}>{u.attention_count || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>
        Conversations{" "}
        <label style={{ fontSize: 14, fontWeight: "normal" }}>
          <input type="checkbox" checked={onlyFlagged} onChange={(e) => setOnlyFlagged(e.target.checked)} />
          {" "}needs attention only
        </label>
      </h3>
      <table>
        <thead>
          <tr>
            <th>Thread</th>
            <th>User</th>
            <th>Last message</th>
            <th>Flag</th>
          </tr>
        </thead>
        <tbody>
          {conversations.filter((c) => !onlyFlagged || c.needs_attention).map((c) => (
            <tr key={c.id} onClick={() => openConvo(c.id)} style={{ cursor: "pointer" }}>
              <td>{c.id}</td>
              <td>{c.user_name}</td>
              <td>{c.last_message}</td>
              <td className={c.needs_attention ? "flag" : ""}>
                {c.needs_attention ? `${c.attention_kind || "flag"}: ${c.attention_reason}` : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {active && (
        <div className="thread-inspect">
          <div className="panel">
            <h3>
              Conversation {active.id} · {active.user_name}
            </h3>
            {active.needs_attention && (
              <p className="flag">
                {active.attention_kind}: {active.attention_reason}{" "}
                <button onClick={() => resolve(active.id)}>Mark resolved</button>
              </p>
            )}
            {active.active_scenario && (
              <p className="mono">Active what-if (not saved): {JSON.stringify(active.active_scenario)}</p>
            )}
            {active.messages.map((m) => (
              <p key={m.id}>
                <b>{m.role}:</b> {m.content}
              </p>
            ))}
          </div>
          <div className="panel">
            <h3>Agent runs</h3>
            {active.runs.map((r) => (
              <div key={r.id}>
                <p>
                  #{r.id} {r.status} · total {Math.round(r.total_ms)} ms · model{" "}
                  {Math.round(r.model_ms)} ms · tools {Math.round(r.tool_ms)} ms · other{" "}
                  {Math.round(r.overhead_ms)} ms · {r.llm_calls} model call(s) · tokens {r.prompt_tokens}/
                  {r.completion_tokens}
                  {r.used_fallback ? " · fallback" : ""}
                </p>
                {r.error_message && <p className="flag">{r.error_message}</p>}
                {r.tools.map((t) => (
                  <div key={t.id} className="mono">
                    {t.tool_name}({JSON.stringify(t.arguments)}){" "}
                    {!t.ok ? "FAILED" : t.blocked ? "needs clarification" : "ok"}{" "}
                    {t.hypothetical ? "(what-if) " : ""}· {Math.round(t.duration_ms)} ms
                    {"\n"}
                    {t.result_preview}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
