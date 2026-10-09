"""Measure end-to-end latency and where the time goes, per request category.

Usage (from backend/):
    PYTHONPATH=. python scripts/measure_latency.py --reps 5
    PYTHONPATH=. python scripts/measure_latency.py --reps 5 --model openai/gpt-4o-mini \
        --price-in 0.15 --price-out 0.60          # USD per 1M tokens, from the OpenRouter model page

Every number comes from the agent_runs/tool_calls rows the app itself records:
  total   = wall time inside run_agent
  model   = sum of the model calls (network + generation)
  tools   = sum of tool executions (SQL + math)
  other   = total - model - tools (graph overhead, prompt building, DB writes)
Output: a markdown table to paste into docs/LATENCY.md, plus latency_results.json.
Without OPENROUTER_API_KEY it measures the keyword fallback (model = 0), which is NOT the real system.
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import sys

from scripts.harness import Client

# (category, user, message) - run in this order inside one conversation per rep, so follow-ups are realistic
WORKLOAD = [
    ("lookup", "U001", "Show me my retail properties"),
    ("analysis", "U001", "How much of my portfolio is retail?"),
    ("lookup", "U001", "Which of my properties is worth more than 10 crore?"),
    ("follow-up", "U001", "Which one is performing better?"),
    ("what-if", "U001", "What if I exclude the Bandra property?"),
    ("what-if", "U001", "How would that change my portfolio?"),
    ("write", "U001", "Update the Bandra property's value to 13 Cr"),
    ("analysis", "U001", "What is my total portfolio value now?"),
]


def pct(values: list[float], q: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, round(q * (len(s) - 1)))] if s else 0.0


def summarize(rows: list[dict]) -> dict:
    def col(k):
        return [r[k] for r in rows]

    return {
        "n": len(rows),
        "total_p50": pct(col("total"), 0.5), "total_p95": pct(col("total"), 0.95), "total_mean": st.fmean(col("total")),
        "model_p50": pct(col("model"), 0.5), "tools_p50": pct(col("tools"), 0.5), "other_p50": pct(col("other"), 0.5),
        "llm_calls_mean": st.fmean(col("llm_calls")),
        "prompt_tokens_mean": st.fmean(col("prompt_tokens")), "completion_tokens_mean": st.fmean(col("completion_tokens")),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url")
    ap.add_argument("--token")
    ap.add_argument("--model")
    ap.add_argument("--reps", type=int, default=3, help="repetitions of the whole workload")
    ap.add_argument("--warmup", type=int, default=1, help="throw-away turns before measuring (connection setup)")
    ap.add_argument("--price-in", type=float, help="USD per 1M prompt tokens")
    ap.add_argument("--price-out", type=float, help="USD per 1M completion tokens")
    ap.add_argument("--out", default="latency_results.json")
    args = ap.parse_args()

    client = Client(args.base_url, args.model, args.token)
    try:
        real = bool(client.health().get("openrouter"))
        print(f"Mode: {'REAL MODEL' if real else 'FALLBACK (no API key) - not representative of production'}\n")
        for _ in range(args.warmup):
            client.chat("U002", "hello")
        rows: list[dict] = []
        for rep in range(args.reps):
            client.reset()
            cid = None
            for category, user, message in WORKLOAD:
                reply = client.chat(user, message, cid)
                cid = reply["conversation_id"]
                run = client.last_run(cid)
                rows.append({
                    "category": category, "message": message, "rep": rep,
                    "total": run["total_ms"], "model": run["model_ms"], "tools": run["tool_ms"], "other": run["overhead_ms"],
                    "llm_calls": run["llm_calls"], "prompt_tokens": run["prompt_tokens"], "completion_tokens": run["completion_tokens"],
                    "status": run["status"], "fallback": run["used_fallback"],
                })
            print(f"rep {rep + 1}/{args.reps} done")
        ok = [r for r in rows if r["status"] == "ok"]
        errors = len(rows) - len(ok)

        overall = summarize(ok)
        by_cat = {c: summarize([r for r in ok if r["category"] == c]) for c in dict.fromkeys(w[0] for w in WORKLOAD)}
        cost = None
        if args.price_in is not None and args.price_out is not None:
            cost = (overall["prompt_tokens_mean"] * args.price_in + overall["completion_tokens_mean"] * args.price_out) / 1_000_000

        ms = lambda x: f"{x:,.0f}"  # noqa: E731
        lines = [
            f"Measured on {len(ok)} successful turns ({errors} errors), model `{args.model or 'default from .env'}`, "
            f"{'real OpenRouter calls' if real else 'FALLBACK mode (no model)'}.",
            "",
            "| Category | n | p50 total (ms) | p95 total (ms) | model p50 | tools p50 | other p50 | model calls | prompt / completion tokens |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
        for name, s in [("**all**", overall), *by_cat.items()]:
            lines.append(
                f"| {name} | {s['n']} | {ms(s['total_p50'])} | {ms(s['total_p95'])} | {ms(s['model_p50'])} | {ms(s['tools_p50'])} | "
                f"{ms(s['other_p50'])} | {s['llm_calls_mean']:.1f} | {s['prompt_tokens_mean']:.0f} / {s['completion_tokens_mean']:.0f} |"
            )
        if cost is not None:
            lines += ["", f"Estimated cost per turn: ${cost:.5f} (~${cost * 1000:.2f} per 1,000 turns) at the prices you supplied."]
        report = "\n".join(lines)
        print("\n" + report)
        with open(args.out, "w") as fh:
            json.dump({"real_model": real, "model": args.model, "overall": overall, "by_category": by_cat, "cost_per_turn_usd": cost, "rows": rows}, fh, indent=2)
        print(f"\nRaw rows written to {args.out}")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
