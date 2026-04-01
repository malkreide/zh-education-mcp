# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-04-01

### Added
- Initial release
- `zh_edu_list_schulgemeinden`: List all school communities and Schulkreise in Canton Zurich
- `zh_edu_schulkreis_trend`: Pupil trend by school district (anchor query: Schulkreis Letzi)
- `zh_edu_overview`: Canton-wide learner overview by school level (2000–present)
- `zh_edu_sek1_profil`: Secondary I profile per school community (Sek A/B/C breakdown)
- `zh_edu_staatsangehoerigkeiten`: Nationality structure of pupils per school community
- `zh_edu_maturitaetsquote`: Gymnasium graduation rates by municipality, district, canton
- `zh_edu_wohnort_trend`: Learner trend by place of residence (Bezirk / Gemeinde)
- `zh_edu_mittelschulen`: Secondary school statistics (Gymnasium, FMS, HMS)
- 24h in-memory cache matching annual BISTA update cycle (Stichtag 15. September)
- Dual transport: stdio (Claude Desktop) + SSE (cloud / Railway)
- Pydantic v2 input validation on all tools
- Bilingual documentation: README.md (EN) + README.de.md (DE)
- Mocked test suite with respx (6 unit tests)
- Phase 1: No-auth data sources only (BISTA public API)
