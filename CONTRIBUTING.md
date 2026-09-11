# Contributing to pdlc-agnostic

Thanks for your interest. This project is small and opinionated, so a little coordination goes a long way.

## Ground rules

- **Discuss before you build.** Open an issue for anything beyond a typo or a small schema fix. Say what problem you hit and what you propose. Large unsolicited pull requests are hard to review and may not land.
- **Keep the spine invariant.** The three phases, append-only logs, HITL gates as the only path to irreversible actions, idempotent mutations, retry-pivot-escalate, and the Phase 0 fallback are not up for per-adapter change. Adapters add mechanism and guardrails, never process. If you think the spine itself is wrong, open a design issue and reference `DESIGN.md`.
- **Stay architecture-neutral in the core.** Skills, agents and schemas must not name a specific product or vendor. Vendor-specific content belongs in an adapter under `adapters/architecture/` or `adapters/shipping/`.
- **Adapters must be safe to publish.** No internal hostnames, account ids, real email addresses, or proprietary runbooks. Use `example.com` style placeholders.
- **No secrets, ever.** Not in files, not in git history. The pre-commit guard the plugin scaffolds for target repos is a good habit here too.

## How to contribute

1. Fork the repository and create a branch from `main`.
2. Make your change. For a new adapter, copy the closest reference adapter and follow `adapters/ADAPTER-CONTRACT.md` or `adapters/SHIPPING-CONTRACT.md` exactly; the CI validator checks manifests and frontmatter.
3. Update `CHANGELOG.md` under "Unreleased".
4. Run the validator locally if you have Python 3: `python3 -m pip install pyyaml && python3 .github/scripts/validate.py`.
5. Open a pull request. Describe the problem, the change, and how you tested it (a real project run is the best evidence).

## Style

- Markdown, plain English, short sentences. Skills and agents are prompts, so clarity beats completeness.
- Skill and agent files must start with YAML frontmatter containing `name` and `description`.
- Versioning follows semver. Bump `version` in both `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` in the same commit; CI fails if they disagree.

## Licensing of contributions

By submitting a contribution you agree that it is licensed under the MIT License, the same license as the project, and that you have the right to submit it. No separate CLA is required.

## Reporting a security issue

See `SECURITY.md`.
