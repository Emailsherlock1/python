# Changelog

## 0.3.0

The client is now generated from the EmailSherlock OpenAPI spec (raw client +
pydantic models in `emailsherlock._generated`), with a thin hand-maintained
sugar layer on top. The v0.2.0 public surface still works.

### Added

- `client_id` option and `with_client_id()` send the `X-Client-Id` header, so a provider account's key can work inside one of its tenants. The current id is readable as `client.client_id`.
- `es.credits()` reads the account status (credit buckets, rate limit, plan, sandbox flag).
- `es.verify.submit_job(emails=...)` and `es.verify.get_job(job_id)` for asynchronous verification jobs.
- `es.guard.record_events(events)` records Email-Guard decision events.
- `decision` result field on single and batch results.
- `is_verify_result(item)` type guard for batch entries; all model types are exported.

### Changed

- **Now depends on `urllib3`, `pydantic`, `python-dateutil`, `typing-extensions`** (was zero-dependency). Minimum Python is 3.9 (was 3.8). This is the trade-off for generating the client from the spec instead of hand-maintaining it.
- Named error classes (`AuthenticationError`, `InsufficientCreditsError`, `RateLimitError`, …), `credits_remaining`, `rate_limit`, and the `ES_KEY` / `EMAILSHERLOCK_API_KEY` env fallback are unchanged.
- Result attributes keep the wire names (`catch_all`, `mx_record`, `free_email`, `checked_at`), same as 0.2.0. `VerifyResult` remains as an alias of the generated `VerifyResultResponse`; `batch().results` is still a flat list of results / per-item errors.
- `ValidationError` now also covers `404` (job not found).

## 0.2.0

Verify response v2 fields on the hand-written client. `VerifyResult` gains `deliverable`, `reason`, `mx_record`, `free_email`, `checked_at` and a `domain` object (`VerifyDomain`: types, trust score, SPF/DKIM/DMARC and other mail-security signals). The new fields are `None` on older API responses.

### Fixed

- A result with `score: null` (verdict `unknown`) no longer raises.

## 0.1.0

Initial release: `verify.single` / `verify.batch`, named error classes, credit and rate-limit accessors. Zero dependencies.
