# Contributing

This repository contains the runtime, guided Windows launcher, firmware target, reproducible project tests, documentation, and finished print/showcase assets. Generation/render scripts, hardware validation helpers, packaging tools, reports, and native working scenes belong in an ignored local `tooling/` folder. They are not part of the public distribution.

Open a focused issue or pull request with reproducible steps and the exact board revision. Use synthetic usage data. Never attach credentials, account identifiers, home paths, raw logs/events, flash backups, or live account screenshots.

## Required pull request format

Use a descriptive title such as `fix: retain the last quota value during a timeout`. Accepted prefixes are `feat`, `fix`, `docs`, `hardware`, `build`, `ci`, `test`, `refactor`, and `chore`. Use 10-90 characters after the prefix. Avoid vague titles such as "updates" or "fix stuff".

Complete the PR template's **Purpose**, **Implementation**, **Validation**, and **Checklist** sections. Explain the concrete problem, resulting behaviour, trade-offs, exact test/build commands and results, and anything not verified. Include before/after images for visible UI/CAD changes, using simulated data. Link related issues. Keep changes focused; open a draft when validation or design is still incomplete.

The automated description check validates structure and a completed checklist. It cannot judge whether a description or test claim is truthful or adequate. Maintainer review must evaluate the evidence.

## Required validation

From an isolated Python environment:

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m compileall -q bridge
python -m platformio run
```

Add or update meaningful tests for changed behaviour. Do not use credentials, live accounts, physical USB, or model calls in automated tests. Keep fixture data synthetic. CI runs the bridge tests on Windows and builds firmware against the pinned Heltec target. CI must pass even for documentation-only PRs; no path filter silently skips required checks.

For firmware, hardware, or CAD changes, state the exact board revision, dimensions, print/slicer settings, and physical checks actually performed. If a device or physical print was unavailable, say so and leave that verification pending. A local build does not prove device behaviour, physical fit, or provider-account compatibility.

## Review and merge rules

- Open a pull request targeting `main`; do not push unreviewed community changes directly.
- Require the **pr-quality**, **bridge**, and **firmware** GitHub Actions checks, with the branch up to date before merging.
- Community PRs require **one approving review**. New commits dismiss stale approvals, and the latest push requires approval by someone other than its pusher.
- Resolve all review conversations. Explain changes made in response to review.
- Use squash merges or rebase merges to keep linear history. Force-pushes and deletion of `main` are disabled.
- The sole repository owner has a documented PR-review exception so owner-authored maintenance PRs do not become impossible to merge. Required CI checks still apply to the owner. Any exception must keep the validation evidence visible; it does not waive tests or builds.

Maintainers may request more evidence or decline changes whose security, compatibility, or maintenance cost exceeds their benefit. Passing CI is necessary, not a promise of merge.

Provider adapters must use supported interfaces, keep credentials with the provider client, reject missing/malformed quota values, and preserve freshness. Do not scrape credential caches or silently start model turns to estimate allowance. Preserve existing user settings when linking integrations.

Contributions use the project's MIT license. Third-party assets require clear redistribution rights and attribution.
