import { useId, useState } from "react";
import { Link } from "react-router-dom";

// Locked state of the business desk. Presentational only: Dashboard.jsx owns the token,
// the validation request and the sessionStorage handling.

function Mark() {
  return (
    <svg viewBox="0 0 32 32" width="34" height="34" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="portfly-mark" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#128c7e" />
          <stop offset="1" stopColor="#075e54" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill="url(#portfly-mark)" />
      <path d="M8 24V13l6-4v15M14 24V8l6 3v13M20 24v-8l4 2v6" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

const ALERT_ICON = {
  invalid: "!",
  server: "⚙",
  network: "↯",
  info: "i",
};

export default function DeskLock({ token, onTokenChange, onSubmit, checking, message, kind }) {
  const [reveal, setReveal] = useState(false);
  const uid = useId();
  const inputId = `${uid}-token`;
  const alertId = `${uid}-alert`;
  const hasProblem = Boolean(message) && kind !== "info";

  return (
    <div className="auth">
      <section className="auth-card" aria-labelledby={`${uid}-title`}>
        <div className="auth-brand">
          <Mark />
          <span>Portfly</span>
        </div>

        <p className="auth-eyebrow">Restricted area</p>
        <h2 id={`${uid}-title`}>Business Desk Access</h2>
        <p className="auth-lead">
          Conversation transcripts, agent activity and portfolio data are limited to authorized Portfly team members.
          Enter your access token to continue.
        </p>

        <form onSubmit={onSubmit} noValidate>
          <label htmlFor={inputId}>Access token</label>
          <div className="auth-field">
            <input
              id={inputId}
              name="desk-token"
              type={reveal ? "text" : "password"}
              value={token}
              onChange={(e) => onTokenChange(e.target.value)}
              placeholder="Paste your token"
              autoComplete="off"
              autoCapitalize="off"
              autoCorrect="off"
              spellCheck={false}
              autoFocus
              disabled={checking}
              aria-invalid={hasProblem && kind === "invalid" ? "true" : undefined}
              aria-describedby={message ? alertId : undefined}
            />
            <button
              type="button"
              className="auth-toggle"
              onClick={() => setReveal((v) => !v)}
              aria-pressed={reveal}
              aria-label={reveal ? "Hide token" : "Show token"}
            >
              {reveal ? "Hide" : "Show"}
            </button>
          </div>

          <div id={alertId} role={hasProblem ? "alert" : "status"} aria-live="polite">
            {message && (
              <p className={`auth-alert ${kind}`}>
                <span className="auth-alert-icon" aria-hidden="true">{ALERT_ICON[kind] || "!"}</span>
                <span>{message}</span>
              </p>
            )}
          </div>

          <button type="submit" className="auth-submit" disabled={checking || !token.trim()} aria-busy={checking}>
            {checking && <span className="spinner" aria-hidden="true" />}
            {checking ? "Verifying…" : "Unlock desk"}
          </button>
        </form>

        <div className="auth-foot">
          <span>The token is kept for this browser tab only and cleared when you close it.</span>
          <Link to="/">Back to chat</Link>
        </div>
      </section>
    </div>
  );
}
