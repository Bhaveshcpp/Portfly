# Latency

## Measurement Status

A local Windows benchmark was conducted using SQLite and real OpenRouter model calls.

- **Model configured:** `nvidia/nemotron-3-ultra-550b-a55b:free`
- **Workload:** 8 requests per repetition across lookup, analysis, follow-up, what-if, and write categories.
- **Repetitions:** 5
- **Successful turns:** 25 out of 40
- **Failed turns:** 15 out of 40
- **Failure cause:** OpenRouter returned HTTP 429 (`free-models-per-day` quota exceeded).

The latency statistics below include only successful turns. These are preliminary measurements from a local environment, not production load-test results.

## Measured Latency

| Category | Successful turns | p50 total (ms) | p95 total (ms) |
| --- | ---: | ---: | ---: |
| All requests | 25 | 9,934 | 24,013 |
| Lookup | 7 | 7,133 | 18,799 |
| Analysis | 6 | 5,297 | 16,098 |
| Follow-up | 3 | 16,770 | 24,013 |
| What-if | 6 | 10,870 | 26,619 |
| Write/update | 3 | 6,148 | 11,058 |

## Latency Breakdown

| Metric | Measured result |
| --- | ---: |
| Overall model time, p50 | 9,865 ms |
| Overall tool execution time, p50 | 2 ms |
| Overall other overhead, p50 | 84 ms |
| Average model calls per successful turn | 1.8 |
| Average prompt tokens per successful turn | 7,381 |
| Average completion tokens per successful turn | 345 |

Model inference and network latency dominate the measured response time. Tool execution and other application overhead were comparatively small in this workload.

## Reliability and Limitations

- 25 successful turns provide an initial latency baseline, but the sample is limited.
- The 15 failed turns were excluded from latency statistics.
- The provider quota prevented reliable completion of the entire workload.
- Token-cost estimates have not been finalized because the applicable pricing has not been verified.
- A later benchmark should verify quota availability, successful real-model execution, and the configured model identifier before recording updated measurements.

## Measurement Plan

When OpenRouter access is available:

1. Run `python -m scripts.measure_latency --reps 5 --warmup 0` from the `backend/` directory.
2. Confirm successful turns used real-model inference rather than fallback responses.
3. Record p50 and p95 latency, model time, tool time, overhead, model-call count, and token usage.
4. Record the model identifier and applicable input/output token prices.
5. Compare results against this baseline and document the measurement environment and sample size.

## Scaling Considerations

- Use a cost-effective model that meets the quality requirements.
- Cache portfolio metrics per user and invalidate the cache after writes.
- Batch tool results where appropriate to reduce model round trips.
- Deploy PostgreSQL and the API with appropriate process management and monitoring.
- Introduce model routing only when measured traces demonstrate a meaningful quality or latency benefit.
