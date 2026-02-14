# Coherence Diagnostic — Status

**Version:** 1.1.0
**Updated:** 14 February 2026, 19:05
**Repository:** https://github.com/koher-architecture/coherence-diagnostic

---

## Current State

✅ **Pushed to GitHub** — v1.1.0 live

---

## Recent Commits

| Commit | Message |
|--------|---------|
| `c7fe726` | Update URL pattern to [toolname]-demo.koher.app |
| `3515caf` | v1.1.0: Add user management system and comparison modes |

---

## URL Structure

**Live URL:** `https://coherence-demo.koher.app`

**Pattern for all Koher tools:** `[toolname]-demo.koher.app`

| Tool | URL | CapRover App |
|------|-----|--------------|
| Coherence Diagnostic | `coherence-demo.koher.app` | `coherence-demo` |
| Bug Report Diagnostic | `bugreport-demo.koher.app` | `bugreport-demo` |
| Meeting Notes Diagnostic | `meetingnotes-demo.koher.app` | `meetingnotes-demo` |
| Job Posting Diagnostic | `jobposting-demo.koher.app` | `jobposting-demo` |

**Main website:** `koher.app` (CapRover app: `koher-site`)

---

## v1.1.0 Features (14 February 2026)

| Feature | Status |
|---------|--------|
| User management (SQLite) | ✅ Complete |
| Admin panel (`/admin`) | ✅ Complete |
| Usage counter (10 analyses/user) | ✅ Complete |
| Daily limit (10 new users/day) | ✅ Complete |
| Three-mode toggle (Koher/Direct/Side-by-Side) | ✅ Complete |
| Sample concepts button | ✅ Complete |
| History tabs (Koher/Direct AI) | ✅ Complete |
| 60-second timeout with refresh prompt | ✅ Complete |
| Auto-loading of `.env` file | ✅ Complete |
| CHANGELOG.md | ✅ Created |
| Git LFS for model files | ✅ Configured |

---

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | Haiku API for Stage 3 diagnosis |
| `DEMO_PASSWORD` | Password for demo users |
| `ADMIN_PASSWORD` | Password for `/admin` panel |

---

## Deployment

```bash
# Create tarball
/opt/homebrew/bin/bash make-deploy-tar.sh

# Output: coherence-diagnostic.tar (725 MB)
# Upload to CapRover app: coherence-demo
```

---

## Next Steps

- Deploy to CapRover instance
- Configure DNS for coherence-demo.koher.app
- Create initial admin users
- Test on production environment
