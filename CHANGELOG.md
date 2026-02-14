# Changelog

All notable changes to Coherence Diagnostic will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.0] — 2026-02-14

### Added

- **User management system** with SQLite database
  - Each password = unique user with 10 lifetime analyses
  - Maximum 10 new users created per day
  - Remaining analyses counter shown to users
- **Admin panel** (`/admin`)
  - Password-protected admin access
  - Create new user passwords
  - View all users with usage stats
  - Dashboard with daily and total statistics
- **Three-mode analysis toggle**
  - Koher Architecture (3-stage pipeline)
  - Direct AI (single Claude call)
  - Side-by-Side comparison
- **Sample concepts button** with strong/weak/middle examples
- **History tabs** separating Koher and Direct AI analyses
- **60-second timeout** with refresh prompt
- **Auto-loading of `.env`** file via python-dotenv

### Changed

- Blues/Teals colour palette (distinct from Koher orange)
- API responses now include `remaining_analyses` field
- Button disables and shows "Limit Reached" when analyses exhausted

### Fixed

- Button hover colours now use teal (`#2d6980`) not orange

---

## [1.0.0] — 2026-02-13

### Added

- Initial release
- DeBERTa model for concept classification (98.38% accuracy)
- Stage 2 deterministic rules
- Stage 3 Haiku diagnosis with streaming
- Password-protected demo access
- Local history storage
- Docker and CapRover deployment configs

