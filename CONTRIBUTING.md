# Contributing

This repository contains the small runtime, guided Windows launcher, firmware target, documentation, and finished print/showcase assets. Development generators, validation harnesses, packaging scripts, reports, and native scenes belong in a local ignored `tooling/` folder; do not add them to publication by accident.

Open a focused issue or pull request with reproducible steps and the exact board revision. Use synthetic usage data. Never attach credentials, account identifiers, home paths, raw logs/events, flash backups, or live account screenshots.

For runtime changes, verify Python syntax, provider failure/staleness behaviour, and the firmware build. For hardware or CAD changes, include board measurements, print settings, and actual fit evidence when available. CI compiles Python and builds the pinned firmware; it cannot prove physical fit or provider account behaviour.

Provider adapters must use supported interfaces, keep credentials with the provider client, reject missing/malformed quota values, and preserve freshness. Do not scrape credential caches or silently start model turns to estimate allowance. Preserve existing user settings when linking integrations.

Contributions use the project's MIT license. Third-party assets require clear redistribution rights and attribution.
