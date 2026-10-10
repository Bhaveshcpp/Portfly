import { useEffect, useState } from "react";
import { api, getDeskToken, setDeskToken } from "./api.js";
import DeskLock from "./DeskLock.jsx";

export default function Dashboard() {
  const [overview, setOverview] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [users, setUsers] = useState([]);
  const [active, setActive] = useState(null);
  const [onlyFlagged, setOnlyFlagged] = useState(false);
  // Start locked when this tab holds no token, so a first visit makes no pointless 401 request.
  const [locked, setLocked] = useState(() => !getDeskToken());
  const [tokenInput, setTokenInput] = useState("");
  const [checking, setChecking] = useState(false);
  const [authMessage, setAuthMessage] = useState("");
  const [authKind, setAuthKind] = useState("info");

  function showAuthProblem(kind, message) {
    setAuthKind(kind);
    setAuthMessage(message);
    setLocked(true);
  }

  // 401/503 from a desk endpoint means: show the lock screen instead of failing silently.
  function handleAuthError(err) {
    if (err.status !== 401 && err.status !== 503) return false;
    const hadToken = Boolean(getDeskToken());
    setDeskToken(""); // never keep a token the server rejected
    if (err.status === 503) {
      showAuthProblem("server", "The business desk isn't configured on the server yet. The administrator needs to set DESK_TOKEN.");
    } else if (hadToken) {
      showAuthProblem("invalid", "Your saved token is no longer valid. Please enter it again.");
    } else {
      showAuthProblem("info", "");
    }
    return true;
  }

  // The desk only opens after the SERVER accepts the token on a protected endpoint.
  async function unlock(e) {
    e.preventDefault();
    const candidate = tokenInput.trim();
    if (!candidate || checking) return;
    setChecking(true);
    setAuthMessage("");
    setDeskToken(candidate); // api() reads it from sessionStorage and sends it as a Bearer header
    try {
      const dash = await api("/api/dashboard");
      setOverview(dash);
      setTokenInput("");
      setLocked(false); // re-enables polling, which loads the rest of the desk
    } catch (err) {
      setDeskToken("");
      if (err.status === 401) {
        setAuthKind("invalid");
        setAuthMessage("That token wasn't accepted. Check it and try again.");
      } else if (err.status === 503) {
        setAuthKind("server");
        setAuthMessage("The business desk isn't configured on the server yet. The administrator needs to set DESK_TOKEN.");
      } else {
        setAuthKind("network");
        setAuthMessage("Couldn't reach the server. Check your connection and try again.");
      }
    } finally {
      setChecking(false);
    }
  }

  async function refresh() {
    try {
      const [dash, convos, people] = await Promise.all([
        api("/api/dashboard"),
        api("/api/conversations"),
        api("/api/users"),
      ]);
      setOverview(dash);
      setConversations(convos);
      setUsers(people);
    } catch (err) {
      if (!handleAuthError(err)) console.error(err);
    }
  }

  async function resolve(id) {
    try {
      await api(`/api/conversations/${id}/resolve`, { method: "POST" });
      await refresh();
      setActive(await api(`/api/conversations/${id}`));
    } catch (err) {
      if (!handleAuthError(err)) console.error(err);
    }
  }

  useEffect(() => {
    if (locked) return undefined; // no polling while waiting for the token
    refresh();
    const id = setInterval(refresh, 8000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locked]);

  async function openConvo(id) {
    try {
      setActive(await api(`/api/conversations/${id}`));
    } catch (err) {
      if (!handleAuthError(err)) console.error(err);
    }
  }

  if (locked) {
    return (
      <DeskLock
        token={tokenInput}
        onTokenChange={setTokenInput}
        onSubmit={unlock}
        checking={checking}
        message={authMessage}
        kind={authKind}
      />
    );
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
