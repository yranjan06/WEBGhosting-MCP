# Security Policy

## Supported Versions

| Version | Supported |
|---|---|
| Latest `main` | ✅ |
| Older releases | ❌ |

## Reporting Vulnerabilities

If you discover a security vulnerability in Go-WebMCP, please report it responsibly:

1. **Do NOT** open a public issue
2. **Email** the maintainer directly at the email address listed on the [GitHub profile](https://github.com/yranjan06)
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will respond within **48 hours** and aim to release a fix within **7 days** for critical issues.

## Security Best Practices

When using Go-WebMCP, please follow these guidelines:

### API Keys

- **Never** hardcode API keys in source code
- Use environment variables: `export AI_API_KEY="your-key"`
- Use `.env` files (see `.env.example`) — they are `.gitignore`'d
- Use different keys for development and production

### Browser Sessions

- `BROWSER_USER_DATA_DIR` persists cookies/sessions on disk — protect this directory
- In production, run with `BROWSER_HEADLESS=true`
- Clear sessions periodically if scraping sensitive sites

### Proxy Configuration

- Use `HTTP_PROXY` for rotating proxies in production
- `PROXY_USERNAME`/`PROXY_PASSWORD` are stored in memory only, never logged
- Use authenticated proxies to avoid IP bans

### Network Security

- When running in SSE mode (`--port=8080`), the server accepts connections from any origin
- **Do not** expose the SSE port to the public internet without authentication
- Use a reverse proxy (nginx, Caddy) with auth if external access is needed

### Plugin Security

- Plugins in `extensions/` execute JavaScript in the browser context
- **Review all plugin code** before deploying — malicious JS can access page data
- Only install plugins from trusted sources

## Scope

The following are **in scope** for security reports:
- Remote code execution via MCP tool input
- Authentication bypass
- Data exfiltration through the browser engine
- Plugin sandbox escapes
- Sensitive data exposure in logs

The following are **out of scope**:
- Issues in upstream dependencies (Playwright, Go stdlib)
- Rate limiting or anti-bot detection by target websites
- Denial of service via excessive tool calls (expected behavior for a browser tool)
