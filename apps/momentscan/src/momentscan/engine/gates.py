"""Gate catalog — the DECISION layer, declared as data (sibling to analyzers.py).

Lives in engine/ next to analyzers.py (Q3, struct-s2): the "sibling to analyzers.py"
self-declaration is now literal — both are the S2-substrate declaration layer, one
naming the PRODUCERS, the other the DECISIONS taken over their measurements.

analyzers.py declares the PRODUCERS (what measures what). This declares the
GATES: the admit / reject / route decisions taken over those measurements. The
distinction is NOT binary-vs-continuous (a binary analyzer output like
`face_present` is still a measurement); it is **reject/route (gate) vs measure
(analyzer)** — "a reject lives only in a gate". A third node type sits between
them: a `Reference` — a per-run cohort statistic (e.g. the identity baseline a
gate compares against), which is neither a context-free analyzer nor a decision.

Why this exists: gate logic used to be inline boolean masks inside the engines
(and re-implemented, driftingly, in the inspector). Pulling it into one ordered
LADDER makes the whole staged decision visible at a glance — what gate, in which
tier, reading which signal, rejecting/routing for which product — and lets the
engine + the inspector read the SAME verdict (`evaluate` → gate_trace.parquet),
so they cannot drift.

The LADDER is declared in EXECUTION ORDER (top-to-bottom = the order it computes,
= the order you read it). `evaluate(signals)` runs it per subject and returns
every gate mask + reference + a per-frame `reason`; `trace_rows` is the
gate_trace schema. Predicates are imperative callables (no DSL) reading a context
`G(name)` that resolves a name to its signal or its already-computed gate value.

TIERS (the staging — only T3 is per-view, which is why gating is non-uniform):
  T0_validity  is this a real, unoccluded face of THIS subject  (universal reject)
  T1_quality   is it a usable capture                            (floor)
  T2_routing   which view does it serve                          (router, not reject)
  T3_policy    what the synthetic query demands                  (per-view relaxed)
"""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
import polars as pl

from momentscan.readings import signals
from momentscan.readings.emotion import EM_ALL as EM, fused_valence
from momentscan.readings.pose import POSE_MAX_DEG, euler_from_transform, fuse_pose, pose_class
from momentscan.store.stash import (
    clip_dir, read_features, read_headpose, read_landmarks, read_parse,
    read_tubelets, write_gate_trace,
)

log = logging.getLogger("momentscan.gates")

# ── gate parameters (the calibrated thresholds the predicates read) ──────────
# pose thresholds (POSE_MAX/FRONTAL/SIDE/CORROB) + the view quantizer now live in
# pose.py — the pose DOMAIN home; the ladder subscribes.
BLINK_MAX, JAW_MAX = 0.45, 0.5
BLUR_FLOOR_FRAC = 0.5   # T1 sharpness VALIDITY floor = this × the subject's median blur
BLUR_MIN_FRAMES = 10    # tracks shorter than this have a noisy median → no floor (pass all)
IDDEV_MARGIN = 0.12   # T0: reject side/quarter frames deviating past the clean baseline
# id_valid (nearest-SUBJECT self-resemblance) — re-admits peak/profile moments the
# frontal-neutral id_ok over-filters, while keeping its occlusion/wrong-person rejection.
TAU_SELF = 0.42       # strong self-resemblance: re-admit any pose at/above this cos to own admit-centroid
TAU_LO = 0.30         # relaxed self floor, allowed ONLY when pose_class=="side" independently explains the depression
TAU_CREF = 0.32       # anchor_trust: a subject whose frontal-neutral self-deviation exceeds this has a GARBAGE centroid → its cos_self is meaningless (subject-level misdetect)
SNO_DELTA = 0.05      # self_not_other margin: frame must beat the nearest RIVAL subject centroid by this
TAU_GROSS = 0.15      # gross occlusion/garbage floor (the RELATIVE-attribution path). When a RIVAL exists,
                      # self_not_other already proved the frame is decisively closer to its OWN centroid than
                      # to any other subject — an expression/pose-INVARIANT identity call the absolute cos
                      # cannot make. So the absolute floor relaxes from TAU_SELF (0.42) to this gross level:
                      # it now only rejects near-orthogonal embedding GARBAGE, not the turned/laughing GOOD
                      # anomalies a distance-from-neutral cut over-kills (247 frames over 9 clips were closer
                      # to self than any rival yet died at the 0.42 floor). SINGLE-subject (no rival → no
                      # margin guard) keeps the strict TAU_SELF/TAU_LO path. See clean-ref-polarity memory.
MIN_SIDE_RUN = 3      # T2: a side frame counts only inside a time-contiguous run ≥ this
ENT_FLOOR = 4.5       # T1: skin luminance-histogram entropy (ISO/IEC 29794-5 "DynamicRange",
                      # bits) floor over the landmark soft-Gaussian skin region. Below it the
                      # face is photometrically DESTROYED — a washout/crush COLLAPSE of the
                      # tonal spread, not merely flat. tone-INVARIANT (no luminance term).
EXPR_CONF_MIN = 0.30  # T3: HSEmotion dominant-category prob floor (portrait query). Below it the
                      # softmax is muddled = NO single coherent expression = caught mid-transition/
                      # unposed = an ambiguous PORTRAIT moment (the geometric obj is blind to it),
                      # the expression analog of a mid-blink. NaN / no-blendshape (profile) → pass.

# ── ② portrait QUERY-PROXIMITY — the authored DEFAULT query ───────────────────
# A point in canonical (blink, smile, jaw) blendshape space = "warm PFP": eyes open ·
# soft smile · mouth mostly closed. A frame admits to portrait only when its expression
# sits within QUERY_DIST_MAX of this target (per-dim weighted L2). Pose is deliberately
# NOT in the query — it stays view-routing, so quarter/side diversity survives. Render-
# query: q lives in the SAME blendshape coords as the generation rig → Blender-renderable.
# Seasonal / user queries = a different target here (preset-authorable later).
PORTRAIT_QUERY = {"blink": 0.0, "smile": 0.35, "jaw": 0.10}
PORTRAIT_QUERY_W = {"blink": 1.0, "smile": 1.0, "jaw": 0.5}   # eyes + smile primary, mouth secondary
QUERY_DIST_MAX = 0.38   # weighted-L2 admit band around the query. Calibrated on the 9-clip corpus:
                        # 0 subjects starved (min 15 query-pass frames), median subject drops from the
                        # ~73% validity floor to a genuinely selective admit — the discriminating ② switch.

TIERS = ("T0_validity", "T1_quality", "T2_routing", "T3_policy")

# the closed vocabulary of per-frame verdicts (gate_trace.reason). Single source —
# the inspector's color map must cover exactly these. Adding a verdict = here + the
# routing list (_VIEW_ROUTE) or the reject tail in _reason() + the inspector GCOL.
REASONS = ("admit", "quarter", "side",
           "reject:identity", "reject:no_face", "reject:blur", "reject:exposure",
           "reject:ambiguous", "no_view")
# colors + the served-view set travel WITH the vocabulary, so the inspector's gate
# lane is GENERATED from this (not a hand-kept JS literal) — it structurally cannot
# hold a different gate vocabulary than the engine. Edit a verdict here, inspector follows.
REASON_COLORS = {
    "admit": "#5ac85a", "quarter": "#7ed957", "side": "#22ddee",
    "reject:identity": "#d65a5a", "reject:no_face": "#e6783c",
    "reject:blur": "#828282", "reject:exposure": "#d68a2e",
    "reject:ambiguous": "#a878c8", "no_view": "#5a5a5a",
}
SERVED = ("admit", "quarter", "side")   # verdicts that produced a usable view (a "pass")
assert set(REASON_COLORS) == set(REASONS), "REASON_COLORS must cover exactly REASONS"
assert set(SERVED) <= set(REASONS)


@dataclass(frozen=True)
class Reference:
    """A per-run cohort statistic a gate reads (not a measurement, not a decision)."""
    name: str
    reads: str               # the signal it summarises
    over: str                # cohort mask name it reduces across ("all" = every frame)
    fn: Callable             # (G) -> float
    note: str = ""
    kind: str = "reference"


@dataclass(frozen=True)
class Gate:
    name: str
    tier: str                # one of TIERS
    semantics: str           # "floor" | "reject" | "router" | "policy"
    reads: tuple[str, ...]   # signals / references / upstream gates it consumes
    applies_to: tuple[str, ...]   # products it is meant to govern (declared intent)
    fn: Callable             # (G) -> np.ndarray[bool] per-frame mask
    note: str = ""
    kind: str = "gate"


def _id_self(G):
    """Nearest-SUBJECT self-resemblance rescue (the complement to id_ok's frontal-neutral
    baseline). id_ok over-filters the person's peak/profile moments (a laugh or a profile
    deviates from the neutral anchor → high iddev → rejected though it IS them). The fix is
    an EMBEDDING check: a frame still closer to its OWN ArcFace centroid than to any rival,
    above a gross-drift floor, IS this person regardless of pose/expression. Guards keep id's
    occlusion/wrong-person rejection: anchor_trust drops subjects whose own anchor is garbage
    (a self-consistent misdetect track), self_not_other drops frame-level impostors, and a
    cos_self floor drops occlusion/look-away/washout.

    Identity is RELATIVE, not absolute: distance-from-own-neutral conflates the GOOD anomalies
    we want (a laugh / a turned profile — far from neutral but clearly THIS person) with the BAD
    ones (occlusion / wrong person). The relative test (closest-to-self by margin) is the
    expression/pose-invariant identity call; the absolute cos_self is only a gross garbage floor.
    So two admit paths: (strong) a high absolute self-cos, side-relaxed — the ONLY guard when no
    rival exists; (relative) a RIVAL present + self_not_other already decisive → the absolute floor
    drops to the gross TAU_GROSS, re-admitting the turned/laughing good anomalies the 0.42 floor
    over-killed. Purely WIDENS id_valid (an added OR term) — cannot reject a currently-served frame.
    EMOTION-dominance is deliberately NOT read here — it is a SELECTION preference (a confident
    NEUTRAL occlusion outscores a real laugh), not an identity signal; it lives in select.py."""
    cs = np.nan_to_num(G("cos_self"), nan=-1.0)          # no embedding → fails every floor
    co = G("cos_other")
    anchor = float(G("clean_ref")) <= TAU_CREF
    self_not_other = ~np.isfinite(co) | (cs - np.nan_to_num(co, nan=-1.0) >= SNO_DELTA)
    side = G("pose_class") == "side"
    strong = (cs >= TAU_SELF) | (side & (cs >= TAU_LO))   # absolute path (no-rival guard)
    relative = np.isfinite(co) & (cs >= TAU_GROSS)        # rival + decisive margin (self_not_other) → gross floor only
    return anchor & self_not_other & (strong | relative)


# ── the ladder — three execution STAGES, declared in logical = dependency order ──
# ① VALIDITY (query-independent, shared by ALL products) → ② portrait POLICY (the
# query-proximity gate) → ③ view ROUTING. evaluate_validity() runs ONLY stage ①, so
# likeness/highlight consume `valid` WITHOUT inheriting portrait's query. The stage
# split is what un-tangles the old flat ladder: clean_ref (a ① reference) used to
# reduce `over` frontal_pose (a ② policy gate) — a T0→T3 inversion that forced the
# whole order backwards. It now reduces over `frontal_clean` (a derived GEOMETRIC
# cohort: pose_class==frontal & have_bs), so ① is self-contained and computes first.

VALIDITY_LADDER: tuple = (   # ① shared, query-INDEPENDENT — "a real, unoccluded face of THIS subject"
    Reference("blur_floor", "blur", "all",
              lambda G: (BLUR_FLOOR_FRAC * float(np.nanmedian(G("blur")))
                         if int(np.isfinite(G("blur")).sum()) >= BLUR_MIN_FRAMES else float("-inf")),
              "T1 sharpness VALIDITY floor = BLUR_FLOOR_FRAC × the subject's median blur — drops only "
              "DESTROYED/smeared frames, not ride-soft ones (a bumpy attraction makes slight blur the "
              "normal case). The sharpness PREFERENCE — pick the crispest capture — lives in select.py's "
              "face_blur ranking, not in this gate. Short tracks (noisy median) → no floor."),

    Gate("sharp_ok", "T1_quality", "floor", ("blur", "blur_floor"), ("portrait",),
         lambda G: np.nan_to_num(G("blur"), nan=G("blur_floor")) >= G("blur_floor"),
         "above the subject's blur floor (NaN → floored in, not failed)"),

    Gate("exposure_ok", "T1_quality", "floor", ("skin_entropy", "mask_valid"), ("portrait",),
         lambda G: (~G("mask_valid")) | (np.nan_to_num(G("skin_entropy"), nan=ENT_FLOOR) >= ENT_FLOOR),
         "photometric VALIDITY floor: skin luminance-histogram entropy (ISO/IEC 29794-5 "
         "DynamicRange) ≥ ENT_FLOOR. A washed-out/crushed face collapses the tonal spread; "
         "a merely flat-but-readable face stays well above (that is an aesthetic 0-axis "
         "matter, NOT a reject). tone-invariant (no luminance term). ¬mask_valid (skin "
         "region too small to trust the histogram) → unjudgeable → pass, never reject. "
         "NB: entropy is darkness-BLIND (an underexposed-but-recoverable face keeps internal "
         "gradient → high entropy); that is the DARK analog of flat-bright-readable = aesthetic "
         "0-axis, deprioritized in per-subject SELECTION ranking (face_micro), not rejected here "
         "— an absolute face-detail floor does not transfer across cameras (resolution-confounded)"),

    # a Reference's full dependency set is {reads} ∪ {over} — `over` (the cohort mask)
    # is also a read; clean_ref reduces over `frontal_clean`, a DERIVED geometric cohort
    # (NOT the ② frontal_pose policy gate) — the cut that keeps ① query-independent.
    Reference("clean_ref", "iddev", "frontal_clean",
              lambda G: (float(np.nanmedian(G("iddev")[G("frontal_clean")])) if G("frontal_clean").any()
                         else float(np.nanmedian(G("iddev")))),
              "T0 identity baseline = median self-deviation over the policy-FREE clean-frontal cohort "
              "(frontal_clean = pose_class==frontal & have_bs). Decoupled from the T3 frontal_pose gate "
              "so validity is query-independent — the cut that un-tangles the tier order. The looser "
              "cohort (no eyes/expr/jaw/cone policy) is ~byte-identical: 8 valid-flips over 9.6k frames."),

    Gate("id_ok", "T0_validity", "reject", ("iddev", "clean_ref"),
         ("portrait", "likeness", "highlight"),
         lambda G: G("iddev") <= G("clean_ref") + IDDEV_MARGIN,
         "looks like this person by the frontal-neutral baseline (a hand-filled box is an "
         "ArcFace outlier). NOTE this over-filters peak/profile moments → id_valid widens it; "
         "kept as a declared node so the trace shows the baseline test"),

    Gate("id_valid", "T0_validity", "reject",
         ("id_ok", "cos_self", "cos_other", "clean_ref", "pose_class"),
         ("portrait", "likeness", "highlight"),
         lambda G: G("id_ok") | _id_self(G),
         "self-resemblance identity validity (SUPERSEDES id_ok inside `valid`): id_ok's frontal-"
         "neutral baseline over-filters the person's better-than-usual peak/profile moments; a "
         "nearest-SUBJECT embedding check (cos to own admit-centroid) re-admits them while "
         "anchor_trust + self_not_other + a gross-drift cos_self floor keep id's occlusion/wrong-"
         "person rejection. Emotion is NOT read here — preference, not validity (→ select.py)"),

    Gate("face_or_fashion", "T0_validity", "reject",
         ("face_present", "sunglasses", "masked"), ("portrait",),
         lambda G: G("face_present") | G("sunglasses") | G("masked"),
         "parse found facial structure, OR the empty face is explained by a worn item"),

    Gate("valid", "T0_validity", "reject", ("face_or_fashion", "have_bs", "id_valid"),
         ("portrait", "likeness", "highlight"),
         lambda G: G("face_or_fashion") & (G("have_bs") | G("id_valid")),
         "real unoccluded face of THIS subject: face structure/fashion present AND "
         "(MediaPipe fit a coherent face → it IS a real face, admit regardless of "
         "ArcFace expression drift — fixes a laugh/cheer being ID-rejected for its "
         "head-back embedding drift; OR id_valid confirms identity by self-resemblance "
         "where there is NO fit). So id_valid guards ONLY the no-fit path (profiles/"
         "occlusion, where have_bs is False — the side bin keeps a genuine profile, the "
         "embedding floor drops occlusion). THE shared ① verdict — likeness/highlight "
         "consume this (via evaluate_validity), inheriting validity but NOT portrait policy)"),
)

def query_dist(get) -> np.ndarray:
    """Per-frame weighted-L2 distance of the expression from the authored portrait
    query — THE ② metric, single home: the query_ok gate, the gate_trace observable
    and portrait's ③ warm ranking all call this, so adding a query dim = one
    PORTRAIT_QUERY entry and every consumer inherits it. `get` maps signal name →
    per-frame array (the ladder ctx G, or a signals-dict `__getitem__`). NaN where
    no blendshape fit (→ query_ok's have_bs guard passes it)."""
    d2 = 0.0
    for name, target in PORTRAIT_QUERY.items():
        d2 = d2 + PORTRAIT_QUERY_W[name] * (np.asarray(get(name), float) - target) ** 2
    return np.sqrt(d2)


POLICY_LADDER: tuple = (   # ② portrait QUERY-PROXIMITY gate — NOT inherited by likeness/highlight
    Gate("eyes_ok", "T3_policy", "policy", ("blink", "sunglasses"), ("portrait",),
         lambda G: G("sunglasses") | (G("blink") < BLINK_MAX),
         "eyes-open — but UNDER SUNGLASSES the check is skipped (fashion route, not "
         "a defect); a declared node so the threshold + the sunglasses route are visible"),

    Gate("query_ok", "T3_policy", "policy",
         ("blink", "smile", "jaw", "have_bs", "pose_class"), ("portrait",),
         lambda G: (~G("have_bs")) | (G("pose_class") == "side")
                   | (np.nan_to_num(query_dist(G), nan=0.0) <= QUERY_DIST_MAX),
         "the DEFAULT warm-PFP query: per-frame expression (blink·smile·jaw) proximity to the "
         "authored target (eyes-open · soft-smile · mouth-closed) within QUERY_DIST_MAX. This is "
         "portrait's REAL ② discriminator — generalises eyes_ok (blink IS a query dim). Profiles "
         "(pose_class==side) / no-blendshape (have_bs False) pass: the expression query is a "
         "frontal/quarter concern, pose diversity lives in routing. q is preset-authorable (render-query)"),

    Gate("expr_ok", "T3_policy", "policy", ("have_bs", "pose_class", "em_conf"), ("portrait",),
         lambda G: (~G("have_bs")) | (G("pose_class") == "side")
                   | (np.nan_to_num(G("em_conf"), nan=1.0) >= EXPR_CONF_MIN),
         "coherent-expression query: HSEmotion dominant prob ≥ EXPR_CONF_MIN — a muddled softmax "
         "is an ambiguous PORTRAIT moment (mid-transition/unposed), the expression analog of a "
         "mid-blink. Applies ONLY to the frontal/three-quarter blendshape path; profiles "
         "(pose_class==side, or have_bs False / no emotion read) pass — emotion is unreliable "
         "off-frontal and energy, not coherence, is highlight's axis. NaN em_conf (no features "
         "stage) → pass → byte-identical to emotion-blind behaviour"),

    Gate("frontal_pose", "T3_policy", "policy",
         ("have_bs", "pose_finite", "eyes_ok", "expr_ok", "query_ok", "jaw", "sharp_ok", "exposure_ok", "yaw_f", "pit_f", "rol_f"),
         ("portrait",),
         lambda G: (G("have_bs") & G("pose_finite") & G("eyes_ok") & G("expr_ok") & G("query_ok") & (G("jaw") < JAW_MAX)
                    & G("sharp_ok") & G("exposure_ok")
                    & (np.abs(G("yaw_f")) < POSE_MAX_DEG) & (np.abs(G("pit_f")) < POSE_MAX_DEG)
                    & (np.abs(G("rol_f")) < POSE_MAX_DEG)),
         "the default frontal query: blendshapes + eyes-open + coherent-expression + query-proximity + jaw + exposure + within the pose cone"),
)

ROUTING_LADDER: tuple = (   # ③ portrait view ROUTING — rep + frontal / quarter / side bins
    Gate("admit", "T2_routing", "router", ("frontal_pose", "valid"), ("portrait",),
         lambda G: G("frontal_pose") & G("valid"),
         "frontal-query survivor (rep + frontal bin)"),

    Gate("quarter_ok", "T2_routing", "router",
         ("have_bs", "pose_finite", "eyes_ok", "expr_ok", "query_ok", "jaw", "sharp_ok", "exposure_ok", "valid"), ("portrait",),
         lambda G: (G("have_bs") & G("pose_finite") & G("eyes_ok") & G("expr_ok") & G("query_ok") & (G("jaw") < JAW_MAX)
                    & G("sharp_ok") & G("exposure_ok") & G("valid")),
         "three-quarter L/R bins: blendshapes still fit, any in-cone pose, coherent expression + query-proximity"),

    Gate("side_raw", "T2_routing", "router", ("pose_class", "sharp_ok", "exposure_ok", "valid"),
         ("portrait",),
         lambda G: (G("pose_class") == "side") & G("sharp_ok") & G("exposure_ok") & G("valid"),
         "profile candidate: pose_class==side (MP+6D quantizer — 6D≥SIDE corroborated by MP "
         "or MP-dropout), before persistence. Replaces the single-scalar |yaw_f|≥SIDE cut that "
         "mislabeled MP-compressed three-quarter-reading profiles as non-side."),

    Gate("side_ok", "T2_routing", "router", ("side_raw", "fx"), ("portrait",),
         lambda G: _sustained(G("side_raw"), G("fx"), MIN_SIDE_RUN),
         "profile bin: a side candidate sustained over a time-contiguous run"),
)

# the full ladder = the three stages concatenated (execution = logical order).
LADDER: tuple = VALIDITY_LADDER + POLICY_LADDER + ROUTING_LADDER

_BY_NAME = {n.name: n for n in LADDER}

# the per-frame signals evaluate() requires in its `signals` dict — the ladder's
# INPUT CONTRACT. The engine ASSEMBLES these inline (renamed/fused from raw
# producers: crop_blur→blur, identity_deviation→iddev, MediaPipe + 6DRepNet yaw
# →yaw_f, parse eye_lum_rel/mouth_vis→sunglasses/masked/face_present), so a gate
# read is checked against THIS, never analyzer.produces (whose namespace is disjoint
# by construction). pose_6d is a trace-only input (pose_src), read by no gate.
SIGNAL_INPUTS = frozenset({
    "fx", "blink", "smile", "jaw", "blur", "iddev", "yaw_f", "pit_f", "rol_f",
    "sunglasses", "masked", "face_present", "pose_6d", "skin_entropy", "skin_frac",
    "mp_yaw_raw", "sixd_yaw_raw",   # raw per-backend yaw → the pose_class quantizer
    "cos_self", "cos_other",        # ArcFace cos to own / nearest-rival admit-centroid → id_valid
    "em_conf",                      # HSEmotion dominant-category prob → expr_ok (coherent expression)
    "em_vel",                       # HSEmotion L1 Δsoftmax — trace-only (read by no gate; portrait's stab tiebreak)
})
_DERIVED = frozenset({"have_bs", "pose_finite", "mask_valid", "pose_class", "frontal_clean"})   # computed in _derive() from signals


def gate_drift() -> list[tuple[str, str]]:
    """Every gate/reference `reads` (and a Reference's `over` cohort mask) must
    resolve to a ladder node, a SIGNAL_INPUT, or a derived signal — else the ladder
    reads something nothing provides. Closes the gate-side blind spot (gates were in
    no drift test). Returns (severity, message); [] = consistent."""
    resolvable = set(_BY_NAME) | SIGNAL_INPUTS | _DERIVED
    problems: list[tuple[str, str]] = []
    for n in LADDER:
        reads = (n.reads,) if isinstance(n.reads, str) else tuple(n.reads)
        for r in reads:
            if r not in resolvable:
                problems.append(("error", f"gate/ref {n.name!r} reads {r!r} — not a ladder node, a SIGNAL_INPUT, or a derived signal"))
        over = getattr(n, "over", "")
        if over and over != "all" and over not in resolvable:
            problems.append(("error", f"reference {n.name!r} reduces `over` {over!r} — not a ladder node"))
    return problems


# fail fast: the ladder cannot import while reading a signal nothing provides.
assert not [m for s, m in gate_drift() if s == "error"], \
    "gate ladder reads an unresolvable signal: " + "; ".join(m for s, m in gate_drift() if s == "error")


def by_tier(tier: str) -> list:
    return [n for n in LADDER if getattr(n, "tier", None) == tier]


class _Ctx:
    """Resolves a name to its computed gate value if present, else its raw signal —
    so a predicate reads `G('blink')` (signal) and `G('valid')` (gate) uniformly."""
    __slots__ = ("s", "v")

    def __init__(self, signals: dict):
        self.s = signals
        self.v: dict = {}

    def __call__(self, name):
        return self.v[name] if name in self.v else self.s[name]


# view routing priority — declared ONCE (side before quarter: |yaw|≥SIDE routes to
# the side bin even when blendshapes also fit). Adding a view gate = one pair here,
# NOT a new branch hand-frozen into _reason (that second copy is how the original
# "REJECT blur on a served side frame" drift happened).
_VIEW_ROUTE = (("side", "side_ok"), ("quarter", "quarter_ok"))
assert {lbl for lbl, _ in _VIEW_ROUTE} <= set(REASONS)   # routing labels are declared verdicts


def _reason(v: dict) -> list[str]:
    """Per-frame verdict in tier order: reject tiers (T0 then T1) first, then which
    view served it (from _VIEW_ROUTE). Drawn from the SAME masks the ladder produced,
    so there is no second hand-frozen copy of the routing to drift."""
    admit, valid, sharp_ok = v["admit"], v["valid"], v["sharp_ok"]
    exposure_ok, expr_ok = v["exposure_ok"], v["expr_ok"]
    fof = v["face_or_fashion"]
    out = []
    for k in range(len(admit)):
        if admit[k]:
            r = "admit"
        elif not valid[k]:
            # valid = face_or_fashion & (have_bs | id_valid); not-valid is either no face
            # at all, or (no MediaPipe fit AND not self-resembling).
            r = "reject:no_face" if not fof[k] else "reject:identity"        # T0
        elif not sharp_ok[k]:
            r = "reject:blur"                                               # T1 quality
        elif not exposure_ok[k]:
            r = "reject:exposure"                                          # T1 quality
        elif not expr_ok[k]:
            r = "reject:ambiguous"                                         # T3 portrait query
        else:
            r = next((label for label, m in _VIEW_ROUTE if v[m][k]), "no_view")  # T2 routing
        out.append(r)
    return out


def _derive(G: "_Ctx") -> None:
    """The derived measurement booleans (pure signal-AVAILABILITY) every gate reads —
    inputs, not decisions; kept in the result so the trace can show them. Shared by
    evaluate_validity (①) and evaluate (full), so the two cannot diverge on them.
    (eyes_ok used to live here too but it carries a threshold + a fashion route, so it
    is now a declared ② policy gate in the ladder, not a hidden derivation.)"""
    s = G.s
    G.v["have_bs"] = np.isfinite(s["blink"])
    G.v["pose_finite"] = np.isfinite(s["yaw_f"])
    # mask_valid: the landmark soft-Gaussian quality region produced a trustworthy
    # reading (the exposure gate reads it; ¬mask_valid → exposure unjudgeable → pass).
    # skin_entropy is NaN when MediaPipe did not fit / the skin region was too small,
    # so finiteness IS the judgeability test (never reject on a missing reading).
    G.v["mask_valid"] = np.isfinite(s["skin_entropy"])
    # view quantizer: {frontal, angle, side} from the two raw backend yaws — side_raw
    # routes on this instead of a single-scalar |yaw_f| cut (recovers MP-compressed profiles).
    G.v["pose_class"] = pose_class(s["mp_yaw_raw"], s["sixd_yaw_raw"])
    # the policy-FREE clean-frontal identity cohort clean_ref reduces over — a derived
    # geometric mask (NOT the ② frontal_pose gate), the cut that keeps ① query-independent.
    G.v["frontal_clean"] = (G.v["pose_class"] == "frontal") & G.v["have_bs"]
    # parse PRESENCE judgeability = the same clean-frontal cohort. The SegFormer
    # face-parsing envelope is frontal-premised — measured on test_0: at |yaw|≈39°
    # it stops segmenting a VISIBLE profile mouth, so "invisible" misreads as "worn
    # mask" (s2 false mask_frac 0.352; frontal-conditioning → 0.000 while the real
    # mask wearer s18 stays 1.000). Off-frontal the worn-item verdicts ABSTAIN
    # (False — no evidence) and presence abstains PASSING (True — never reject on
    # an unjudgeable reading, the mask_valid precedent); the occlusion/wrong-person
    # reject duty falls to id_valid, whose embedding evidence works at any pose.
    jud = G.v["frontal_clean"]
    G.v["sunglasses"] = np.asarray(s["sunglasses"], bool) & jud
    G.v["masked"] = np.asarray(s["masked"], bool) & jud
    G.v["face_present"] = np.asarray(s["face_present"], bool) | ~jud


def evaluate_validity(signals: dict) -> dict:
    """Stage ① — the query-INDEPENDENT validity verdict (a real, unoccluded face of THIS
    subject), the substrate ALL three products share. Runs ONLY VALIDITY_LADDER (+ the
    derived signals): no portrait policy (eyes/expr/pose-cone), no view routing. likeness
    and highlight consume THIS (`valid` / `id_valid`) instead of re-deriving their own
    filtering, inheriting validity WITHOUT inheriting portrait's query. Pure (no I/O)."""
    G = _Ctx(signals)
    _derive(G)
    for node in VALIDITY_LADDER:
        G.v[node.name] = node.fn(G)
    return G.v


def evaluate(signals: dict) -> dict:
    """Run the FULL ladder (① validity → ② portrait policy → ③ view routing) over one
    subject's per-frame signals → every gate mask + reference + a per-frame `reason`.
    Pure (no I/O). `signals` must carry: fx, blink, jaw, blur, iddev, yaw_f, pit_f, rol_f,
    mp_yaw_raw, sixd_yaw_raw, cos_self, cos_other, em_conf, sunglasses, masked,
    face_present (+ pose_6d trace). For the ①-only verdict, call evaluate_validity."""
    G = _Ctx(signals)
    _derive(G)
    for node in LADDER:
        G.v[node.name] = node.fn(G)
    G.v["reason"] = _reason(G.v)
    return G.v


def trace_rows(sid: int, fx, s: dict, v: dict) -> list[dict]:
    """gate_trace.parquet schema — every per-frame gate verdict as data (the
    'declaration that runs' surface the inspector renders). `s` = the signals
    passed to evaluate; `v` = its result."""
    cr = round(float(v["clean_ref"]), 4)
    qd = query_dist(s.__getitem__)   # ② query-proximity distance (observable) — single home
    rows = []
    for k in range(len(fx)):
        rows.append({
            "track_id": int(sid), "frame_idx": int(fx[k]),
            "yaw_f": _r(s["yaw_f"][k]), "pit_f": _r(s["pit_f"][k]), "rol_f": _r(s["rol_f"][k]),
            "pose_src": "6d" if s["pose_6d"][k] else "mp",
            "mp_yaw_raw": _r(s["mp_yaw_raw"][k]), "sixd_yaw_raw": _r(s["sixd_yaw_raw"][k]),
            "pose_class": str(v["pose_class"][k]),
            "frontal_clean": bool(v["frontal_clean"][k]),   # clean_ref's cohort — persisted so consumers read, never re-derive
            "blink": _r(s["blink"][k]), "smile": _r(s["smile"][k]), "jaw": _r(s["jaw"][k]), "blur": _r(s["blur"][k]),
            "iddev": _r(s["iddev"][k]), "clean_ref": cr,
            "sharp_ok": bool(v["sharp_ok"][k]),                                  # T1 quality
            "skin_entropy": _r(s["skin_entropy"][k]), "skin_frac": _r(s["skin_frac"][k]),
            "exposure_ok": bool(v["exposure_ok"][k]), "mask_valid": bool(v["mask_valid"][k]),  # T1 quality
            "id_ok": bool(v["id_ok"][k]), "id_valid": bool(v["id_valid"][k]),
            "cos_self": _r(s["cos_self"][k]), "cos_other": _r(s["cos_other"][k]),
            "em_conf": _r(s["em_conf"][k]), "expr_ok": bool(v["expr_ok"][k]),
            "em_vel": _r(s["em_vel"][k]),   # trace-only: HSEmotion L1 Δsoftmax (portrait's stab tiebreak)
            # EFFECTIVE (judgeability-derived) verdicts, not the raw parse booleans —
            # the trace records what the ladder DECIDED on; raw stays in parse.parquet.
            "face_present": bool(v["face_present"][k]),
            # sunglasses_v / masked_v = the JUDGED (judgeability-derived) worn-item verdicts —
            # portrait reads these to average its fashion dict, no longer re-deriving them.
            "sunglasses_v": bool(v["sunglasses"][k]), "masked_v": bool(v["masked"][k]),
            "fashion": bool(v["sunglasses"][k] or v["masked"][k]), "valid": bool(v["valid"][k]),  # T0
            "have_bs": bool(v["have_bs"][k]), "pose_finite": bool(v["pose_finite"][k]),
            "eyes_ok": bool(v["eyes_ok"][k]),
            "query_dist": _r(qd[k]), "query_ok": bool(v["query_ok"][k]),                 # ② query-proximity
            "admit": bool(v["admit"][k]), "quarter_ok": bool(v["quarter_ok"][k]),
            "side_raw": bool(v["side_raw"][k]), "side_ok": bool(v["side_ok"][k]),  # T2/T3 view
            "reason": v["reason"][k],
        })
    return rows


def _r(x):
    """nan-safe passthrough for the gate trace (NaN → null, not a bogus number). FULL
    precision ON PURPOSE: the inspector now READS these signal columns as channels, and
    ch() auto-ranges the channel min/max from the RAW values — so ANY rounding here
    would make the persisted channel's range differ from the inspector's own recompute
    (its vals round to 4dp but its lo/hi do not). gate_trace is a MACHINE trace read by
    the inspector, not a human file; full precision makes any column a byte-identical
    channel source (the emotion_frame lesson). gate VERDICTS use full-precision sigs in
    evaluate(), unaffected. (float64 either way — no size change, just no rounding.)"""
    return None if not np.isfinite(x) else float(x)


def _sustained(mask: np.ndarray, fx: np.ndarray, min_run: int, max_gap: int = 2) -> np.ndarray:
    """Keep only True frames inside a TIME-contiguous run of ≥ min_run frames.
    Contiguity is frame_idx (gap ≤ max_gap), NOT array position: the per-track
    frame sequence has detection gaps, so two array-adjacent rows can be seconds
    apart. A held profile is a real frame_idx run; a lone 6d spike across a gap is
    dropped (cap_1: 4 isolated → none survive; dual_2 sustained occlusion → caught
    by the T0 gate above, not here)."""
    out = np.zeros_like(mask)
    idxs = np.where(mask)[0]
    if len(idxs) == 0:
        return out
    run = [idxs[0]]
    for k in idxs[1:]:
        if fx[k] - fx[run[-1]] <= max_gap:
            run.append(k)
        else:
            if len(run) >= min_run:
                out[run] = True
            run = [k]
    if len(run) >= min_run:
        out[run] = True
    return out


# ── the gates STAGE — run_gates (R10) ─────────────────────────────────────────
# gate_trace.parquet production is a STAGE (measurement), not a step inside the
# portrait engine. It used to live in products/portrait.py, which made
# likeness/select freshness a hostage to portrait re-running (L9/D2: the inspector
# and likeness read the gate's `valid` verdict, but only portrait produced it). This
# entry assembles each subject's per-frame SIGNALS from the upstream artifacts
# (tubelets/landmarks/crops-blur/parse/headpose6d/features-em_conf), runs the ladder
# (evaluate), and writes the trace — for ALL subjects (aux included: the shared ①
# validity + the aux centroids as cos_other rivals are needed downstream even though
# no product exposes aux). The signal-assembly here is the SAME code portrait used;
# portrait becomes a read_gate_trace reader (R11 commit B).
#
# occlusion (parse.parquet): eye region darker than skin → sunglasses (clear glasses
# ≈ skin); mouth region absent → mask. Preset policy, calibrated on cap_1.
EYE_LUM_MIN, MOUTH_VIS_MIN = 0.7, 0.01
ID_MIN_CENTROID = 10   # a subject needs ≥ this many admit frames for a trustworthy ArcFace
                       # centroid (the nearest-subject id_valid anchor); fewer → no rescue/rival


def _emo_align(ed, fx):
    """Align a subject's emotion to its tubelet frames → (em_conf, vel). em_conf = HSEmotion
    dominant-category prob (the expr_ok gate + the obj anti-ambiguity tiebreak); vel = L1
    Δsoftmax between time-contiguous frames (obj anti-transition tiebreak). NaN where features
    are absent / frame-gap → gate passes, factor 1.0 = no penalty."""
    N = len(fx)
    em_conf = np.full(N, np.nan)
    vel = np.full(N, np.nan)
    if ed is None:
        return em_conf, vel

    posf = {int(f): i for i, f in enumerate(ed["fx"])}
    pmo = ed["emo"]
    for k, f in enumerate(fx):
        i = posf.get(int(f))
        if i is None:
            continue
        em_conf[k] = ed["conf"][i]
        j = posf.get(int(fx[k - 1])) if k > 0 and fx[k] - fx[k - 1] == 1 else None
        if j is not None and np.isfinite(pmo[i]).all() and np.isfinite(pmo[j]).all():
            vel[k] = float(np.abs(pmo[i] - pmo[j]).sum())

    return em_conf, vel


def _open_crop(crops_dir: Path, manifest, sid):
    """VideoCapture for a subject's clean crop track (blur source), or None if absent."""
    f = crops_dir / f"s{sid}.mp4"
    return cv2.VideoCapture(str(f)) if (manifest and f.exists()) else None


def _crop_frame(cap, crop_index, sid, frame_idx):
    """Decode one crop-track frame by its manifest index (None if unavailable)."""
    idx = crop_index.get(sid, {}).get(frame_idx)
    if cap is None or idx is None:
        return None

    cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
    ok, img = cap.read()
    return img if ok else None


def _read_emotion_by_sid(out_root, clip_id) -> dict:
    """Per-subject HSEmotion softmax + em_conf, keyed by track_id → {fx, conf, emo}.
    Empty when the features stage did not run (read_features RAISES) → em_conf NaN
    downstream → expr_ok passes (byte-identical to emotion-blind behaviour)."""
    out: dict = {}
    try:
        from momentscan_features_specialist45d.registry import INDEX
        ff = read_features(out_root, clip_id, "A")
        emi = [INDEX[e] for e in EM]

        for s in ff["track_id"].unique().to_list():
            fs = ff.filter(pl.col("track_id") == s).sort("frame_idx")
            Ms = np.array(fs["feature"].to_list(), float)
            out[int(s)] = {"fx": fs["frame_idx"].to_numpy(),
                           "conf": fused_valence(Ms, INDEX)["em_conf"],
                           "emo": Ms[:, emi]}
    except Exception as e:   # noqa: BLE001 — optional-dependency degrade (features stage / specialist pkg)
        log.debug("gates.emotion.absent", extra={"clip_id": clip_id, "reason": str(e)})
        return {}
    return out


def _frame_readings(fx, sid, lm_bs, lm_tf, hp, cap, crop_index):
    """One subject's per-frame blendshape (blink/jaw/smile), dual-backend pose
    (MediaPipe euler yaw/pit/rol + 6DRepNet yaw6/pit6/rol6), and crop blur. NaN where
    a reading is absent. Returns (blink, jaw, smile, yaw, pit, rol, blur, yaw6, pit6, rol6)."""
    N = len(fx)
    blink = np.full(N, np.nan)
    jaw = blink.copy()
    smile = blink.copy()
    yaw = blink.copy()
    pit = blink.copy()
    rol = blink.copy()
    blur = blink.copy()
    yaw6 = blink.copy()
    pit6 = blink.copy()
    rol6 = blink.copy()

    for k, f in enumerate(fx):
        b = lm_bs.get((sid, int(f)))
        M = lm_tf.get((sid, int(f)))
        if b is not None:
            blink[k] = signals.blink(b)
            jaw[k] = signals.jaw(b)
            smile[k] = signals.smile(b)
        if M is not None:
            yaw[k], pit[k], rol[k] = euler_from_transform(M)
        h = hp.get((sid, int(f)))
        if h is not None:
            yaw6[k], pit6[k], rol6[k] = h
        img = _crop_frame(cap, crop_index, sid, int(f))
        if img is not None:
            blur[k] = signals.crop_blur(img)

    return blink, jaw, smile, yaw, pit, rol, blur, yaw6, pit6, rol6


def _occlusion_signals(occ, sid, fx):
    """parse-derived per-frame worn-item (sunglasses/mask) + face-presence + exposure
    (skin entropy/frac) signals for one subject. These are WORN items, not occlusion to
    reject. Empty occ → all-abstain defaults. Returns (sunglasses, masked, face_present,
    skin_entropy, skin_frac)."""
    N = len(fx)
    sunglasses = np.zeros(N, bool)
    masked = np.zeros(N, bool)
    face_present = np.ones(N, bool)   # parse found SOME facial structure (eyes|mouth>0)
    skin_entropy = np.full(N, np.nan)   # exposure-gate signals
    skin_frac = np.full(N, np.nan)
    if not occ:
        return sunglasses, masked, face_present, skin_entropy, skin_frac

    for k, f in enumerate(fx):
        v = occ.get((sid, int(f)))
        if v is None:
            continue
        eye_rel, mouth_vis, eyes_vis, s_ent, s_frac = v
        if eye_rel is not None and eye_rel < EYE_LUM_MIN:
            sunglasses[k] = True
        if mouth_vis is not None and mouth_vis < MOUTH_VIS_MIN:
            masked[k] = True
        face_present[k] = bool((eyes_vis or 0) > 0 or (mouth_vis or 0) > 0)
        if s_ent is not None:
            skin_entropy[k] = s_ent
        if s_frac is not None:
            skin_frac[k] = s_frac

    return sunglasses, masked, face_present, skin_entropy, skin_frac


def run_gates(out_root, clip_id: str, *, fps: int = 6) -> dict:
    """gates STAGE entry — assemble per-frame signals, evaluate the ladder for every
    subject, write gate_trace.parquet. Behaviour-identical to the block that used to
    run inside portrait.select_portrait (the byte-identical gate_trace is the guard).
    Returns {clip_id, ok, n_rows, n_subjects, ms}."""
    t0 = time.perf_counter()
    cdir = clip_dir(Path(out_root), clip_id)
    tub = read_tubelets(out_root, clip_id).sort(["track_id", "frame_idx"])
    lm = read_landmarks(out_root, clip_id)
    lm_bs = {(r["track_id"], r["frame_idx"]): np.array(r["blendshapes"], float)
             for r in lm.iter_rows(named=True) if r["blendshapes"] is not None}
    lm_tf = {(r["track_id"], r["frame_idx"]): np.array(r["transform"], float).reshape(4, 4)
             for r in lm.iter_rows(named=True) if r["transform"] is not None}

    # crop track (clean container) — blur source. None → degrade.
    crops_dir = cdir / "crops"
    manifest = None
    if (crops_dir / "manifest.json").exists():
        manifest = json.loads((crops_dir / "manifest.json").read_text(encoding="utf-8"))
    crop_index = {s["subject_id"]: {f: i for i, f in enumerate(s["frames"])}
                  for s in (manifest["subjects"] if manifest else [])}

    # occlusion signal (parse.parquet) — optional; gate skips it if absent.
    occ = {}
    pq = read_parse(out_root, clip_id)
    if pq is not None:
        occ = {(r["track_id"], r["frame_idx"]): (r["eye_lum_rel"], r["mouth_vis"], r["eyes_vis"],
                                                 r.get("skin_entropy"), r.get("skin_frac"))
               for r in pq.iter_rows(named=True)}   # .get: tolerate parse.parquet predating skin_entropy

    # full-range pose (6DRepNet) — fills MediaPipe's profile NaN so SIDE faces get a
    # real yaw (adapter already sign-aligned). Optional; absent → frontal-only.
    hp = {}
    hq = read_headpose(out_root, clip_id)
    if hq is not None:
        hp = {(r["track_id"], r["frame_idx"]): (r["yaw"], r["pitch"], r["roll"])
              for r in hq.iter_rows(named=True)}

    emo_by_sid = _read_emotion_by_sid(out_root, clip_id)   # em_conf → expr_ok gate

    # PASS 1 — per-frame signals + PROVISIONAL admit cohort (cos_self/cos_other = NaN).
    # id_valid then ≡ id_ok, and admit = frontal_pose & valid via have_bs, so the admit
    # set is FINAL here (independent of the cos signals it seeds). Those admit frames are
    # the clean cohort each subject's ArcFace centroid is built from.
    ctxs = []
    for sid in sorted(tub["track_id"].unique().to_list()):
        df = tub.filter(pl.col("track_id") == sid).sort("frame_idx")
        fx = df["frame_idx"].to_numpy()
        emb = np.array(df["embedding"].to_list(), float)   # ArcFace — occlusion guard
        N = len(fx)

        cap = _open_crop(crops_dir, manifest, sid)
        blink, jaw, smile, yaw, pit, rol, blur, yaw6, pit6, rol6 = \
            _frame_readings(fx, sid, lm_bs, lm_tf, hp, cap, crop_index)
        if cap is not None:
            cap.release()

        # fused pose + 6D-rescue mask — single home pose.fuse_pose.
        yaw_f, pit_f, rol_f, pose_6d = fuse_pose(yaw, pit, rol, yaw6, pit6, rol6)
        sunglasses, masked, face_present, skin_entropy, skin_frac = _occlusion_signals(occ, sid, fx)

        # SIGNALS → GATES (the declared ladder). iddev is a measurement (clean_ref
        # Reference summarises it); sunglasses/masked/face_present came from parse.
        iddev = signals.identity_deviation(emb)
        em_conf, em_vel = _emo_align(emo_by_sid.get(int(sid)), fx)   # em_conf gates expr_ok; em_vel = trace-only
        _nan = np.full(N, np.nan)
        sig = {"fx": fx, "blink": blink, "smile": smile, "jaw": jaw, "blur": blur, "iddev": iddev,
               "yaw_f": yaw_f, "pit_f": pit_f, "rol_f": rol_f, "pose_6d": pose_6d,
               "mp_yaw_raw": yaw, "sixd_yaw_raw": yaw6,   # raw backends → gates' pose_class
               "cos_self": _nan, "cos_other": _nan.copy(),   # filled in PASS 2 (cross-subject)
               "em_conf": em_conf, "em_vel": em_vel,         # em_conf → expr_ok; em_vel → trace only (portrait tiebreak)
               "sunglasses": sunglasses, "masked": masked, "face_present": face_present,
               "skin_entropy": skin_entropy, "skin_frac": skin_frac}

        admit1 = evaluate(sig)["admit"]
        ctxs.append({"sid": sid, "fx": fx, "emb": emb, "N": N, "sig": sig, "admit1": admit1})

    # CENTROIDS — each subject's clean ArcFace anchor = L2-normalised mean of its admit-frame
    # (L2-normalised) embeddings. < ID_MIN_CENTROID admits → no centroid (no rescue, no rival).
    cents = {}
    for c in ctxs:
        a = c["admit1"]
        if int(a.sum()) >= ID_MIN_CENTROID:
            e = c["emb"][a]
            e = e / (np.linalg.norm(e, axis=1, keepdims=True) + 1e-9)
            m = e.mean(0)
            cents[c["sid"]] = m / (np.linalg.norm(m) + 1e-9)

    # PASS 2 — cos_self / cos_other → final gate verdicts → gate_trace rows (ALL subjects).
    # evaluate() is pure/cheap; re-running it keeps the admit cohort gate-owned.
    rows: list[dict] = []
    for c in ctxs:
        sid, fx, emb, N, sig = c["sid"], c["fx"], c["emb"], c["N"], c["sig"]
        en = emb / (np.linalg.norm(emb, axis=1, keepdims=True) + 1e-9)
        own = cents.get(sid)
        cos_self = en @ own if own is not None else np.full(N, np.nan)
        others = [v for s2, v in cents.items() if s2 != sid]
        cos_other = np.max([en @ v for v in others], axis=0) if others else np.full(N, np.nan)
        sig["cos_self"], sig["cos_other"] = cos_self, cos_other

        gv = evaluate(sig)
        rows += trace_rows(sid, fx, sig, gv)

    write_gate_trace(out_root, clip_id, rows)
    ms = int((time.perf_counter() - t0) * 1000)
    log.info("gates.done", extra={"clip_id": clip_id, "n_rows": len(rows), "n_subjects": len(ctxs)})
    return {"clip_id": clip_id, "ok": True, "n_rows": len(rows), "n_subjects": len(ctxs), "ms": ms}
