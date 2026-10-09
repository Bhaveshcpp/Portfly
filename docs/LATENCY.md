# Latency

## Measurement status

A local Windows run using SQLite and the deterministic fallback reported typical `/api/chat` round trips of approximately **30–80 ms**. In this mode, model time is 0 ms because no OpenRouter model calls are made.

**These measurements do not represent real-model performance.**

Real-model evaluation and latency benchmarking are currently blocked by OpenRouter's `429 free-models-per-day` rate limit. No verified real-model latency or token-cost benchmark is available yet.

## Expected latency (estimates, not measurements)

| Component | Expected latency |
| --- | --- |
| FastAPI and SQL tools | 10–40 ms |
| OpenRouter model call, including generation | 800–2,500 ms |
| Additional model/tool round trip | +400–1,500 ms |
| End-to-end response | Approximately 1–4 seconds |

These figures are estimates and have not been independently measured in the current environment.

## Where time is spent

The model call is expected to dominate end-to-end latency. Database and calculation tools are relatively inexpensive for the current small dataset. Conversation history is capped at 16 messages to bound prompt size.

## Measurement plan

When real-model access is available:

1. Run `scripts/measure_latency.py` with five repetitions.
2. Confirm that successful turns used the real model rather than fallback responses.
3. Record p50 and p95 end-to-end latency, model time, tool time, overhead, model-call count, and token usage.
4. Record the model identifier and applicable input/output token prices.
5. Replace estimates with measured results, preserving the measurement environment and sample size.

## Scaling considerations

- Use a cost-effective model that meets the quality requirements.
- Cache portfolio metrics per user and invalidate the cache after writes.
- Batch tool results where appropriate to reduce model round trips.
- Deploy PostgreSQL and the API with appropriate process management and monitoring.
- Introduce model routing only when measured traces demonstrate a meaningful quality or latency benefit.
