# AI Real Estate Portfolio Analyst — Dataset

## Purpose
Synthetic dataset for the AI Real Estate Portfolio Analyst engineering assignment.

The dataset is intentionally small so candidates can focus on agent design, orchestration, state, tool use, reasoning, reliability and performance rather than data engineering.

## Files

- `users.csv` — synthetic users and high-level preferences.
- `properties.csv` — synthetic property portfolio records.
- `sample_requests.csv` — example conversations and the capability/interpretation expected from the system.

## Important

- All data is fictional and synthetic.
- No private login or authenticated property source is required.
- Currency values are in INR.
- `purchase_price_inr` is intentionally mostly blank; candidates may decide how to handle missing historical purchase data.
- Candidates may use SQL, a relational database, an in-memory store, or another appropriate persistence strategy.
- Candidates should not assume that the examples in `sample_requests.csv` represent the complete set of supported queries.

## Suggested analytical possibilities

The dataset supports questions such as:

- Total portfolio value.
- Portfolio value by property type.
- Retail / residential / office exposure.
- Annual rental income.
- Rental yield where value and rent are available.
- Highest/lowest value property.
- Highest annual rent.
- Geographic concentration.
- Occupancy / vacancy.
- Comparisons between property types.
- Hypothetical portfolio scenarios.

These are examples, not a prescribed feature list.

## Design intent

The property CRUD capability is only the setup layer.

The core product is an AI analyst that understands the user's portfolio and can have an ongoing conversation about it.
