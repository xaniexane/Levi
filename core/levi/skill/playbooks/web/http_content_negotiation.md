---
skill_id: web_http_content_negotiation
name: HTTP Content Negotiation
description: How clients and servers agree on format, language, and encoding using Accept headers and server responses.
risk: info
permissions: []
requires_confirmation: false
tags: [http, fundamentals]
version: 1.0.0
---
# HTTP Content Negotiation
## Purpose
Understand the polite handshake where a client states its preferences and the server picks the best representation it can offer.
## Key ideas
- The client advertises capabilities with Accept (media types), Accept-Language, Accept-Encoding, and Accept-Charset.
- Quality values (q=0.9) rank preferences; the server chooses the highest-ranked type it can produce.
- The server declares its choice with Content-Type, Content-Language, and Content-Encoding on the response.
- If no acceptable representation exists, the server answers 406 Not Acceptable rather than sending something useless.
- The Vary header tells caches which request headers affect the response, so variants do not get mixed up.

## In practice
For most APIs negotiation is simple: the client sends Accept: application/json and the server either complies or returns 406. It gets interesting with multi-format services: one endpoint serving JSON, XML, and CSV based on the Accept header, or localized content keyed off Accept-Language. Whatever you negotiate on, list it in Vary, or a cache will serve the English JSON to someone who asked for French XML. Test negotiation with curl's -H flags; it takes thirty seconds and reveals servers that ignore the client's preferences entirely, which is a bug worth filing.

```http
GET /report HTTP/1.1
Host: api.example.com
Accept: text/csv, application/json;q=0.8

HTTP/1.1 200 OK
Content-Type: text/csv
Vary: Accept
Content-Disposition: attachment; filename="report.csv"

id,name,total
1,Mara,42
```

## Common mistakes
- Ignoring the Accept header and always returning one format, then wondering why content-type errors appear.
- Negotiating on headers without listing them in Vary, so caches serve the wrong variant.
- Returning 200 with a default format when the client explicitly asked for something unsupported, instead of 406.

## Checklist
- Does the server honor Accept, or at least reject what it cannot produce with 406?
- Is Vary set for every request header that changes the response?
- Are quality values handled, not just the first listed type?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
