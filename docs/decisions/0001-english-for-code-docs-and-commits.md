# Use English for code, comments, documentation and commit messages

## Context and Problem Statement

The project is developed with a mix of German-speaking humans and AI agents.
Without a rule, identifiers, comments, documentation and commit messages drift
between German and English, which hurts searchability and readability.

## Decision Drivers

* One language per artefact, no mixing
* Tooling, libraries and the Mealie API are English
* Agents and external contributors must be able to read the history

## Considered Options

* English for everything
* German for everything
* English for code, German for docs and commits

## Decision Outcome

Chosen option: "English for everything", because it matches the
ecosystem (Python, Mealie API, ruff, Typer) and keeps the whole repository in
one language.

This covers identifiers, comments, docstrings, log and error messages, tests,
documentation (README, CLAUDE.md, ADRs) and commit messages. Conversation with the maintainer may stay in German.

### Consequences

* Good, because code, docs, history and tooling output are consistent and searchable.
* Good, because agents and contributors need no language context.
* Bad, because German-only readers must read English commit messages.

## More Information

Format: [MADR](https://adr.github.io/madr/).
