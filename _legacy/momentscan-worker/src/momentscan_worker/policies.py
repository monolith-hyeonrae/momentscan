"""Policies loader — read the JSON files under ``<repo>/policies/`` and
turn them into Python objects + a pre-instantiated visualbind Normalizer.

A *policy* here is one domain decision committed as a JSON file
(signal ranges, statistics config, selector policy). visualbind and
visualstack ship none of these values; the worker injects them at
job start.

The name *policies* avoids collision with portrait981's legacy
``visualbind.CatalogStrategy`` / catalog-of-reference-profiles
vocabulary — there *catalog* is a classifier baseline + a lookup table
of known signatures, which is a completely different thing.

Each JSON file may contain ``_doc`` keys at any nesting depth — these
are stripped before the dict is passed to the framework so the
underlying validation (e.g. :class:`visualbind.Normalizer`) doesn't
see them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from visualbind import Normalizer


SIGNAL_RANGES_FILENAME = "signal_ranges.json"
STATISTICS_CONFIG_FILENAME = "statistics_config.json"
SELECTOR_POLICY_FILENAME = "selector_policy.json"


@dataclass(frozen=True)
class Policies:
    """Snapshot of the domain policies at job-start time."""

    signal_ranges: dict
    statistics_config: dict
    selector_policy: dict
    normalizer: Normalizer

    @property
    def vector_dim(self) -> int:
        return self.normalizer.dim


def _strip_doc(obj):
    """Recursively drop ``_doc`` keys; non-mutating."""
    if isinstance(obj, dict):
        return {k: _strip_doc(v) for k, v in obj.items() if k != "_doc"}
    if isinstance(obj, list):
        return [_strip_doc(v) for v in obj]
    return obj


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_policies(policies_dir: Path) -> Policies:
    """Read every policy file under ``policies_dir`` and build a Policies.

    Raises ``FileNotFoundError`` if any required file is missing — the
    policies dir is supposed to be the *single source of domain truth*;
    a missing file should fail fast rather than silently degrade.
    """
    d = Path(policies_dir).expanduser().resolve()
    if not d.is_dir():
        raise FileNotFoundError(f"policies directory not found: {d}")

    ranges_path = d / SIGNAL_RANGES_FILENAME
    statistics_path = d / STATISTICS_CONFIG_FILENAME
    selector_path = d / SELECTOR_POLICY_FILENAME

    for p in (ranges_path, statistics_path, selector_path):
        if not p.is_file():
            raise FileNotFoundError(f"policy file missing: {p}")

    raw_ranges = _read_json(ranges_path)
    raw_statistics = _read_json(statistics_path)
    raw_selector = _read_json(selector_path)

    # Strip _doc keys at all nesting depths.
    signal_ranges = _strip_doc(raw_ranges)
    statistics_config = _strip_doc(raw_statistics)
    selector_policy = _strip_doc(raw_selector)

    # Eagerly construct the Normalizer — surfaces bad policy values
    # before pipeline assembly rather than mid-stream.
    normalizer = Normalizer(signal_ranges)

    return Policies(
        signal_ranges=signal_ranges,
        statistics_config=statistics_config,
        selector_policy=selector_policy,
        normalizer=normalizer,
    )
