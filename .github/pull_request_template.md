## Purpose

Describe the concrete problem and why this change is needed. Link the related issue when applicable.

## Implementation

Explain the resulting behaviour and the important changes. Include before/after images for visible UI or CAD changes, using simulated data only. State any compatibility, migration, or hardware assumptions.

## Validation

List the exact commands run and their results. For hardware/CAD changes, state the board revision, print settings, and actual checks performed. Clearly identify anything untested.

```text
python -m unittest discover -s tests -v
python -m platformio run
```

## Checklist

- [ ] The title and description explain a specific change.
- [ ] Tests cover changed behaviour and pass locally.
- [ ] The firmware builds with the pinned target, or I have explained why it could not be built.
- [ ] Setup/behaviour documentation is updated where needed.
- [ ] No credentials, account data, private paths, raw events/logs, or flash backups are included.
- [ ] Generation/render/packaging helpers remain in ignored `tooling/`.
- [ ] Limitations and missing physical checks are stated explicitly.
