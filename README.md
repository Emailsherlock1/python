# email-sherlock

Official Python client for the [EmailSherlock](https://emailsherlock.com) email-verification API. Verify one address or a batch over HTTPS with an API key.

Zero third-party dependencies (uses only the standard library). Python 3.8+.

## Install

```bash
pip install email-sherlock
```

The distribution is `email-sherlock`; the import is `emailsherlock`:

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
batch = es.verify.batch(emails=["jane@acme.com", "sales@acme.com"])

for item in batch.results:
    if isinstance(item, VerifyResult):
        print(item.email, item.result)
    else:  # BatchItemError
        print(item.email, "failed:", item.error)
```

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
| `score`      | float | 0–1 confidence, higher is safer to send to                      |
| `freshness`  | str   | `fresh` · `cached_recent` · `cached_stale_refreshed`            |

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
| `ValidationError`           | 400 / 422 | the request body was rejected            |
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
