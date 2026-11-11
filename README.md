# emailsherlock-sdk

Official Python client for the [EmailSherlock](https://emailsherlock.com) email-verification API. Verify one address or a batch over HTTPS with an API key. Get an API key at https://emailsherlock.com/api. Want to try a single address by hand first? The free [email verification](https://emailsherlock.com/verify) tool runs the same checks in the browser.

Python 3.9+. Built on `urllib3` + `pydantic`; the client and models are generated from the OpenAPI spec, with a thin hand-maintained layer for the ergonomics below.

## Install

```bash
pip install emailsherlock-sdk
```

The distribution is `emailsherlock-sdk`; the import is `emailsherlock`:

```python
from emailsherlock import Emailsherlock
```

## Quick start

```python
import os
from emailsherlock import Emailsherlock

# reads the key from the environment, never hard-code it
es = Emailsherlock(api_key=os.environ["ES_KEY"])

result = es.verify.single(email="jane@acme.com")

print(result.result)  # "valid"
print(result.score)   # 0.95
```

Called with no argument, `Emailsherlock()` reads `ES_KEY` (or
`EMAILSHERLOCK_API_KEY`) from the environment.

## Batch

Up to 100 addresses per call:

```python
from emailsherlock import is_verify_result

batch = es.verify.batch(emails=["jane@acme.com", "sales@acme.com"])

for item in batch.results:
    if is_verify_result(item):
        print(item.email, item.result)
    else:  # BatchItemError
        print(item.email, "failed:", item.error)
```

## Async jobs

For large lists, submit a job and poll it. Every address runs the full pipeline
including the SMTP probe, so the results carry definitive inbox verdicts:

```python
import time

job = es.verify.submit_job(emails=["a@acme.com", "b@acme.com"])
while job.status != "completed":
    time.sleep(2)
    job = es.verify.get_job(job.id)

print(job.results)
```

## Account status

```python
account = es.credits()
account.credits.total  # spendable credits
account.sandbox        # True on an es_test_ key
```

## Email-Guard events

Record Email-Guard decision events (free, no credits). The full address is never
sent, only the domain:

```python
es.guard.record_events([
    {"domain": "mailinator.com", "verdict": "disposable", "action": "deny",
     "reasons": ["disposable_provider"], "degraded": False, "source": "local"},
])
```

## Working for a tenant (`X-Client-Id`)

If your key belongs to a provider account, you can run calls inside one of its tenants. Usage, verify jobs (and their refunds), deliverability addresses and Guard events then land on that tenant. Pass the tenant's numeric id as `client_id`, or derive a second client from an existing one:

```python
es = Emailsherlock(api_key=os.environ["ES_KEY"], client_id=1234)
es.verify.single(email="jane@acme.com")

# or: same key, base URL and timeout, a different tenant
other = es.with_client_id(5678)
other.client_id  # 5678
```

`with_client_id()` returns a new client and leaves the original unchanged, so each keeps its own credit and rate-limit readings. Without `client_id` the key works in its own account and no header is sent.

Poll a job with the same client that submitted it. A job submitted for a tenant is only visible with the same `X-Client-Id`.

Failures you can hit:

- 404 `client_not_found` (`ValidationError`): the id is not one your key may reach.
- 403 `forbidden` (`ForbiddenError`): the tenant is blocked from the API.
- 400 `client_id_not_allowed` (`ValidationError`): the key is not a provider key.

Read the server code from `err.code`. A `client_id` that is not a positive integer raises `EmailsherlockError` with code `config_error` before any request is sent.

## The result object

`VerifyResult` mirrors the API JSON:

| attribute    | type  | meaning                                                         |
|--------------|-------|-----------------------------------------------------------------|
| `email`      | str   | the address you sent                                            |
| `result`     | str   | `valid` · `invalid` · `catch_all` · `disposable` · `role` · `unknown` |
| `mx`         | bool  | the domain has reachable MX records                             |
| `disposable` | bool  | throwaway / temporary-mail provider                             |
| `role`       | bool  | role address such as `info@` or `sales@`                        |
| `catch_all`  | bool  | host accepts mail for any local part                            |
| `score`      | float or None | 0–1 confidence, higher is safer to send to. `None` when no confidence could be computed (e.g. `unknown` results) |
| `freshness`  | str   | `fresh` · `cached_recent` · `cached_stale_refreshed`            |
| `deliverable`| bool? | proven via SMTP: True accepted, False provably bad, None unproven |
| `reason`     | str?  | why the pipeline decided (`mailbox_accepts`, `greylisted`, …)   |
| `mx_record`  | str?  | the primary MX host, when one was resolved                      |
| `free_email` | bool? | the domain is a freemail provider                               |
| `checked_at` | str?  | when the verification ran (ISO 8601)                            |
| `domain`     | obj?  | domain-level intelligence (SPF, DKIM, DMARC, score, blacklists, …) |
| `decision`   | obj   | `recommendation` (allow · deny · review) + `reasons`            |

Every field and model is generated from the [OpenAPI spec](https://emailsherlock.com/api/docs); editors autocomplete the full shape.

## Credits and rate limits

After every call:

```python
es.credits_remaining   # e.g. 41
es.rate_limit          # {"limit": 60, "remaining": 59, "reset": 1700000000}
```

## Errors

Every failure raises a subclass of `EmailsherlockError`:

| class                       | HTTP | when                                          |
|-----------------------------|------|-----------------------------------------------|
| `AuthenticationError`       | 401  | missing or invalid API key                    |
| `ForbiddenError`            | 403  | key lacks the endpoint's scope (`required_scope`) |
| `InsufficientCreditsError`  | 402  | not enough credits (`credits_required`, `credits_remaining`) |
| `RateLimitError`            | 429  | rate limit hit (`retry_after`, `limit`, `remaining`, `reset`) |
| `ValidationError`           | 400 / 404 / 422 | the request was rejected, or the job was not found |
| `ServiceUnavailableError`   | 503  | verify engine unavailable (the credit is auto-refunded) |

```python
from emailsherlock import RateLimitError

try:
    es.verify.single(email="jane@acme.com")
except RateLimitError as err:
    print(f"retry after {err.retry_after}s")
```

## License

MIT. Full API reference: https://emailsherlock.com/api/docs
