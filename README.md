# emailsherlock-sdk

Official Python client for the [EmailSherlock](https://www.hostsherlock.com) email-verification API. Verify one address or a batch over HTTPS with an API key. Get an API key at https://www.hostsherlock.com/api. Want to try a single address by hand first? The free [email verification](https://www.hostsherlock.com/verify) tool runs the same checks in the browser.

Zero third-party dependencies (uses only the standard library). Python 3.8+.

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
| `score`      | float or None | 0–1 confidence, higher is safer to send to. `None` when no confidence could be computed (e.g. `unknown` results) |
| `freshness`  | str   | `fresh` · `cached_recent` · `cached_stale_refreshed`            |
| `deliverable` | bool or None | the mailbox accepts mail                                |
| `reason`     | str or None | machine-readable explanation of the result, e.g. `mailbox_accepts`, `mailbox_not_found`, `no_mx`, `bad_syntax`, `disposable_provider`, `role_address`, `catch_all_domain`, `greylisted`, `smtp_timeout`, `smtp_unreachable`, `verification_pending` |
| `mx_record`  | str or None | the primary MX host that answered                       |
| `free_email` | bool or None | the domain is a free-mail provider (Gmail, Outlook, ...) |
| `checked_at` | str or None | ISO 8601 timestamp of the verification                  |
| `domain`     | `VerifyDomain` or None | domain-level intelligence, see below          |
| `raw`        | dict  | the unmodified API JSON                                         |

The fields from `deliverable` down are additive: they are `None` on older
API responses and may be `null` per field when a signal has not been
measured yet.

## Domain intelligence

When the API returns a `domain` object, `result.domain` is a `VerifyDomain`:

| attribute      | type  | meaning                                                       |
|----------------|-------|---------------------------------------------------------------|
| `name`         | str   | the domain that was checked                                   |
| `types`        | list of str or None | `freemail` · `disposable` · `custom` · `company` · `government` · `education` · `public` · `isp` |
| `score`        | float or None | 0–100 domain trust score                              |
| `spf`          | bool or None | a valid SPF record exists                              |
| `dkim`         | bool or None | DKIM is set up                                         |
| `dmarc`        | bool or None | a DMARC record exists                                  |
| `dmarc_policy` | str or None | `none` · `quarantine` · `reject`                        |
| `mta_sts`      | bool or None | MTA-STS policy published                               |
| `tls_rpt`      | bool or None | TLS-RPT record exists                                  |
| `bimi`         | bool or None | BIMI record exists                                     |
| `dane`         | bool or None | DANE/TLSA records exist                                |
| `blacklists`   | int or None | number of DNS blacklists listing the domain or its IPs  |
| `dnssec`       | str or None | `secure` · `insecure` · `bogus`                         |
| `caa`          | bool or None | a CAA record exists                                    |

```python
result = es.verify.single(email="jane@acme.com")

if result.domain is not None:
    print(result.domain.score)         # 87.0
    print(result.domain.dmarc_policy)  # "reject"
```

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

MIT. Full API reference: https://www.hostsherlock.com/api/docs
