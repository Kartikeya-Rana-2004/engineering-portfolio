# Hands-on interview preparation

Before adding the projects to a resume:

1. Run the offline tests and verification script yourself.
2. Load the example batch twice and explain why the second run creates no request rows.
3. Change the open example to a closed record, reload it, and inspect the new duration.
4. Run the intentionally invalid batch and explain why silver remains unchanged.
5. Inspect `requests`, `runs`, `quarantine`, and `daily_service_metrics` in SQLite.
6. Explain the difference between incremental warehouse loading and source CDC, and the stale-replay risk.
7. Change a contract rule and add a test for a failure you expect.

Possible project descriptions after hands-on review, with ownership wording adjusted to your actual work:

- CivicFlow: Developed an AI-assisted Python/SQL portfolio pipeline for NYC 311 records with replay-safe keyed loading, correction handling, quarantine gates, audit lineage, and daily operational reporting; verified on a bounded 12,000-record public-data extraction.
- ContractWatch: Implemented an AI-assisted record-contract and schema-drift checker with type/required-field validation, timestamp consistency, observed-schema baselines, machine-readable failure reports, and automated failure-case tests.

Do not claim AWS experience, distributed processing, production users, business savings, or personally measured outcomes beyond the checked-in evidence. The recorded tests and experiments are software verification, not evidence that you have already completed this walkthrough.
