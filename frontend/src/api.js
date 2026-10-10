const API_BASE_URL = import.meta.env.VITE_API_URL || "";
const TOKEN_KEY = "portfly:desk-token";

// The desk token lives in sessionStorage only: it is forgotten when the tab closes.
export function getDeskToken() {
  try {
    return sessionStorage.getItem(TOKEN_KEY) || "";
  } catch {
    return "";
  }
}

export function setDeskToken(token) {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: the desk will simply ask again */
  }
}

export async function api(path, options = {}) {
  const token = getDeskToken();
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    const err = new Error(text || res.statusText);
    err.status = res.status;
    throw err;
  }
  return res.json();
}
