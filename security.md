# Security posture — Extnded Thotz

## Headers

All responses carry the same hardened header set via `vercel.json`:

- `Content-Security-Policy`: self-only by default; fonts may load from the same origin when served cross-origin for the preload.
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `X-DNS-Prefetch-Control: off`
- `Permissions-Policy`: cameras, microphone, geolocation, payment, USB blocked
- `Cross-Origin-Opener-Policy: same-origin`
- `Cross-Origin-Resource-Policy: same-origin`
- `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`
- `Timing-Allow-Origin: https://extnded-thotz.vercel.app`
- `X-Permitted-Cross-Domain-Policies: none`

## CORS

CORS is not wide open. `Access-Control-Allow-Origin` is set only on font assets
and only to the site origin. Static pages and the download rewrite do not expose
a wildcard origin.

## Reporting

CSP violations are reported to `/csp-report`. A recipient route or external
collector should be wired there before enabling `report-to` in production.

## Security contact

See `.well-known/security.txt` for the responsible disclosure contact and policy URL.

## HSTS preload

The site is preload-ready. Submit at:
https://hstspreload.org/

Do not submit until `Strict-Transport-Security` is live on the canonical host
and all subdomains serve HTTPS.
