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

Verbatim from `ci.yml` — same paths, same flags:

```bash
ruff check src/ tests/ scripts/
ruff format --check src/ tests/ scripts/
```

`tests/` and `scripts/` are gated too, so linting `src/` alone lets CI go red on
files you never checked. Drop `--check` to apply the formatting instead of
verifying it.

`ruff` is pinned in `pyproject.toml` (`dev` extra), and the `pip install -e
".[dev]"` above installs exactly that version. A different `ruff` earlier in your
`PATH` beats the pin without the install saying a word — `python
scripts/check_ruff_pin.py` checks both call paths and runs in CI as well.

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

## Releases

Publishing is not part of a pull request: a GitHub release triggers
[`publish.yml`](.github/workflows/publish.yml), which gates the built artifacts
before the PyPI upload. What it checks and why it sits ahead of the upload is in
[Release](README.md#release).

Two consequences for contributors:

- Leave the `mcp-name:` comment at the bottom of `README.md` alone. It ships as
  the package description, and the gate demands exactly one — removing it or
  writing a second one anywhere in that file breaks the release.
- Versions live in `pyproject.toml`, `server.json` and the README badges.
  [`check_version_sync.py`](scripts/check_version_sync.py) compares them on every
  pull request, so change them together.
