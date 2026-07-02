# momentscan policies

Domain policies injected into the generic visualbind framework. **All
domain vocabulary lives here, not in visualstack / visualbind.**

| File | Owner of decisions | Consumer |
|------|--------------------|----------|
| `signal_ranges.json` | momentscan domain | `visualbind.Normalizer` |
| `statistics_config.json` | momentscan domain | per-subject statistics accumulators (signal / appearance / shape / category) |
| `selector_policy.json` | momentscan domain | selectors (highlight / diversity / standard) |

These are *config*, not code. Changing them must not require a code
change anywhere — visualstack / visualbind read them and apply
mechanically.

The values committed today are **placeholders** matching the open
decisions in `visualstack/docs/redesign-2026-05.md` §9 — refine through
empirical iteration on real source material.

Naming note: the directory is `policies/` rather than `catalog/` to
avoid collision with portrait981's legacy `visualbind.CatalogStrategy`
vocabulary, where *catalog* meant a classifier baseline + a lookup
table of known signatures.
