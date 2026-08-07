# Contributing to zh-education-mcp

🇩🇪 [Deutsche Version](CONTRIBUTING.de.md)

Thank you for your interest in contributing!

## Development Setup

```bash
git clone https://github.com/malkreide/zh-education-mcp.git
cd zh-education-mcp
pip install -e ".[dev]"
```

## Running Tests

```bash
# Unit tests (mocked, no network)
pytest tests/ -m "not live"

# All tests including live API calls
pytest tests/
```

### The live suite: when it runs, and who sees a red result

**Cadence:** every Monday at 05:23 UTC, plus on demand via *Actions → Live-Tests
→ Run workflow*. See [`.github/workflows/live-tests.yml`](.github/workflows/live-tests.yml).

**Who sees it:** a red run opens an issue titled `Live-Tests gegen BISTA rot …`
with the `upstream` label, and comments on the existing one instead of opening a
second. A run that goes green again closes it.

**A red live run does not necessarily mean *our* bug.** It means the contract
with the source has changed, or the source is down. Both belong seen; only the
first belongs fixed. Please read the run before disabling the job — that is how
this check dies, and it is the only one in the repository that can contradict a
wrong assumption about BISTA. Every other test asserts against a fixture, and
the fixture was written from the same assumption as the code.

That is not hypothetical. On 2026-08-03 the code read `r["Schulgemeinde"]` while
BISTA delivered `schulgemeinde` — four of six datasets, eight tools, every unit
test green. It was found by a live run done by hand, because none was scheduled.

The PR run stays at `-m "not live"`: a foreign 503 must not turn an unrelated
pull request red.

## Code Style

```bash
python -m ruff check src/
python -m ruff format src/
```

## Data Sources

This server uses the BISTA public API (`bista.zh.ch/basicapi/ogd/`) — no authentication required.

**No-Auth-First principle**: Phase 1 tools must work without any API key.

## Adding New Tools

1. Validate the API endpoint with `curl` first
2. Add a Pydantic v2 input model
3. Add the tool with `@mcp.tool` decorator and full docstring
4. Add mocked unit tests using `respx`
5. Mark live tests with `@pytest.mark.live`
6. Update CHANGELOG.md

## Submitting Changes

1. Fork the repo
2. Create a branch: `git checkout -b feat/your-feature`
3. Commit: `git commit -m "feat: add xyz tool"`
4. Push and open a Pull Request
