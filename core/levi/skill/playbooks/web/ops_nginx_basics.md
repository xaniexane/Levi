---
skill_id: web_ops_nginx_basics
name: Nginx Essentials
description: The core nginx patterns: server blocks, location routing, proxy_pass, and static file serving.
risk: info
permissions: []
requires_confirmation: false
tags: [ops, deployment]
version: 1.0.0
---
# Nginx Essentials
## Purpose
Configure the web's most common front door for routing, proxying, and serving static assets.
## Key ideas
- server blocks select by Host; location blocks inside them match paths with prefix or regex rules.
- proxy_pass forwards to upstreams; pairing it with header forwarding keeps the app informed.
- nginx serves static files directly and fast; let it, instead of burning app workers on assets.
- try_files elegantly falls through from static file to app route, the classic single-page-app recipe.
- Always test config with nginx -t before reload; a typo should never take down the front door.

## In practice
Organize config as one file per site in sites-available with symlinks from sites-enabled, so enabling a site is reversible and obvious. Prefer prefix locations over regex where possible; they are cheaper and their precedence is easier to reason about. Set explicit proxy timeouts and buffer sizes rather than inheriting defaults that were chosen for someone else's workload. After every change, run the config test and reload (not restart) so existing connections drain gracefully. Keep a staging server block mirroring production; most nginx outages are config edits tested directly on the live box.

```nginx
server {
  listen 443 ssl;
  server_name shop.example.com;

  location /static/ {
    alias /var/www/shop/static/;
    expires 30d;
  }

  location /api/ {
    proxy_pass http://127.0.0.1:8000/;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 30s;
  }

  location / {
    try_files $uri /index.html;
  }
}
```

## Common mistakes
- Editing the live config and restarting without testing, turning a typo into downtime.
- Serving static assets through the app server, wasting workers on bytes nginx serves better.
- Using regex locations by default and getting bitten by their precedence rules.

## Checklist
- Is config tested with nginx -t before every reload?
- Are static assets served directly by nginx?
- Are proxy timeouts and forwarded headers set explicitly?

---
*Original work authored for LEVI. All explanations written fresh; no content copied from external sources.*
