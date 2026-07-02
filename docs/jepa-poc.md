# JEPA PoC — Development Context

> North-star context for momentscan's reorientation (2026-06-08~). The product/PoC
> intent lives here; the *implementation contract* (`Distribution` + readings) lives in
> [`../README.md`](../README.md). Read §3 (guardrails) and §9 (open questions) before
> writing any code. v2 — revised for the multi-person reality (§4, §5, §6 Step 0).
>
> **Session decisions that refine this doc are in the Appendix at the bottom — read it.**

## 1. Goal
PoC for a **self-improving media product** built on an unlabeled video stream from an
outdoor theme-park attraction: ~2,000+ clips/day, **no labels, no labeling budget**.
Clips are multi-person (see §4); outputs are produced **per rider**. Two products:

- **Profile** — the most identity-faithful, flattering portrait frame for a rider.
- **Highlight** — the most compelling few-second moment for a rider.

Long-term intent: the product keeps improving from the data flood with **minimal human
effort**. This PoC validates the core hypotheses *cheaply*, before any heavy training or
feedback-loop infrastructure.

## 2. Two parallel tracks
- **Track A — Frozen-signal (product floor / baseline).** Selection built directly on
  existing specialist signals. Ships, interpretable, no GPU training. This is the
  baseline Track B must beat, and the cold-start taste prior.
- **Track B — JEPA (research bet / ceiling).** Frozen pretrained **V-JEPA 2** features +
  light heads. **No custom pretraining in this PoC.**

Relationship: A is baseline + yardstick + cold-start prior + auxiliary steering signal for
B. Same input, same eval harness, same output schema → **directly comparable**.

## 3. Scope guardrails — do NOT do in this PoC
- **Do NOT** pretrain or continue-train V-JEPA from scratch. Frozen backbone only.
  (Custom SSL is the heaviest, most fragile step; defer until drift *measurably* hurts.)
- **Do NOT** build the sales/feedback loop yet — but **DO** log candidates + decisions in
  a telemetry-ready schema (§8) so it can attach later.
- **Do NOT** attempt full-shot / out-of-frame prediction. Predicting unseen body/background
  in latent space = hallucination; product-risky. Out of scope.
- **Do NOT** depend on system-provided customer IDs (tickets get swapped, IDs unreliable).
- **Do NOT** assume one person per clip, and **do NOT** separate riders by 2D image
  position alone — confirmed insufficient. Identity is **per-person track**, not per-clip
  (see §5, §6 Step 0).

## 4. Data & constraints
- Input: short clips (~1 min), outdoor, vehicle descending a slope, frontal upper-body framing.
- **Multiple people per clip.** Often 2 riders (a **main rider** and an **auxiliary rider**,
  differing by seating position), plus **staff / bystanders** visible at the boarding/start
  point. 2D position does **not** cleanly separate main vs auxiliary; depth estimation has
  been tried to distinguish the rear (auxiliary) rider.
- Wild-data realities (treat as signal, not noise): large **lighting drift**
  (season / weather / time-of-day + ride motion changing face illumination), heavy and
  variable **occlusion** (sunglasses, masks, hats), strong **camera vibration**, **no
  reliable cross-clip identity**.
- **PII**: these are customer faces. Respect retention/masking; do not bake in careless
  raw-face storage. Flag any storage decision for human sign-off.

## 5. Locked design decisions
- **Highlight ≠ max prediction error.** Define highlight as the **conditional residual**:
  deviation that is *surprising given the scene/nuisance-explainable variance*. Naive
  max-error surfaces shake / blur / occlusion-onset, not moments. PoC baseline: subtract a
  simple scene/nuisance model (global motion + brightness) from per-track frame-to-frame
  embedding change; peaks of the *residual* = highlight candidates.
- **Profile = narrow, then rank.** Use the invariant representation to narrow an
  *identity-faithful* candidate set per track (frames close to the per-track identity
  reference, low temporal velocity). Then rank candidates for *portrait quality* using
  specialist signals (frontal pose, eyes open, sharpness, pleasant-expression AU).
  **Don't make the representation do the aesthetic job.**
- **Intra-track invariance for identity (revised).** "One **track** = one person" is the
  ground truth, not "one clip = one person." Detection + tracking (§6 Step 0) produce
  per-person tubelets; the identity reference = robust centroid (trimmed mean / median) of
  a *track's* embeddings, resistant to occlusion outliers. No system ID needed.
- **Subject attribution (rider vs bystander, main vs auxiliary).** Primary discriminator =
  **temporal persistence × scene phase**: segment each clip into boarding (static) vs ride
  (dynamic descent) phases; tracks that persist into/through the *ride* phase = riders;
  tracks present only during boarding = staff/bystanders (drop them). Among riders, split
  main vs auxiliary by depth (front/back) + camera geometry — depth is a **tiebreaker, not
  the primary cut**. *(Superseded — see Appendix A2.)*
- **Multi-person is an asset, not just noise.** Two riders in one vehicle share a
  near-identical forcing function (same drop, same timing). Differences in their face-state
  trajectories are therefore *purely person-conditioned*, not scene-confounded. Same-clip
  rider pairs are a built-in natural experiment for the person-conditioning ablation — use
  them in eval.
- **Conditioning, not stream count.** The factorization core is a *conditioning relation*:
  a stable reference + deviations read against it. 2-factor (invariant content vs dynamic)
  is fine. If/when a predictor is trained, **condition the predictor only, keep the encoder
  latent pure** (V-JEPA-2-AC style).
- **Collapse:** with a frozen backbone this is a non-issue for the PoC. Only relevant if we
  later train.

**Cruxes to watch (what the eval must measure):**
1. *Upstream:* can we get clean enough per-person tracks under occlusion + vibration?
   Tracker ID-switches corrupt track-level invariance. Measure track purity; use embedding
   re-id (see §7, `personmemory`) to stitch broken tubelets.
2. *Core:* in the (frozen) representation, does nuisance become removable while genuine
   emotional spikes survive as surprise (an informative residual)? If yes, the whole JEPA
   story works. If no, profile still survives but highlight-via-surprise collapses to "just
   use AU spikes" and Track A wins highlights.

## 6. First milestones

**Step 0 (shared, before both tracks): per-person tracks + subject attribution.**
- Person/face detection + tracking → per-person tubelets per clip.
- Scene-phase segmentation (boarding vs ride) via global motion/brightness.
- Subject attribution: keep tracks that persist into the ride phase = riders; tag main vs
  auxiliary by depth + geometry; drop boarding-only bystanders/staff.
- Output unit for everything downstream = `(clip_id, track_id, rider_role)`.

**Shared eval harness** (both tracks output to it):
- Per rider track: top-K profile candidates (contact sheet) + top-K highlight clips
  (montage), plus a candidate-log JSON (telemetry-ready, §8).
- Seed eval: developer-picked ~50 good / ~50 bad per product for rough precision.
  **Eval-only, not training labels.** Include same-clip rider pairs (per §5) as a
  person-conditioning probe.

**Track B (per track):**
1. Frozen V-JEPA 2 feature extraction over each tubelet → time-indexed embeddings.
2. Identity reference (robust centroid) → profile candidates (close + low-velocity).
3. Rank candidates via specialist signals → profile pick.
4. Residual-peak highlight baseline (subtract scene/nuisance model from embedding change).

**Track A (per track):**
1. Run existing specialists over each tubelet → 45D signal time series.
2. Profile: heuristic trigger on signals (frontal + eyes open + sharp + pleasant AU).
3. Highlight: within-track anomaly (Mahalanobis on the per-track signal distribution —
   label-free deviation = natural highlight proxy) + AU/motion energy peaks.

**Decision gate after milestones:** does B beat A on the eval set, or win *specifically*
where A fails (heavy occlusion / lighting drift)? That outcome decides whether to invest in
B's heavier path later (domain continued-SSL, a trained predictor).

## 7. Stack / repo
- Monorepo: `reportrait` (brand: *The Reportrait*). Track A extends existing components —
  **read their real interfaces before integrating, do not assume internals**:
  - `visualbind` — specialist ensemble → 45D structured signal vector (AU intensities,
    emotion class, head pose, face-box ratios).
  - `personmemory` — per-person Gaussian tracking (Welford online stats, Mahalanobis
    anomaly detection). **Doubles as re-id** for Step 0: stitch broken tubelets and reject
    ID-switch frames by embedding distance.
  - `momentscan` — frontal-view capture trigger engine (natural home for Track A selection).
  - `depict` — context-aware image/video generation (ComfyUI / RunPod / AWS) — used later
    for output quality, not in the core PoC selection.
- New for Step 0: an off-the-shelf person/face **detector + tracker**; optional **monocular
  depth** as a main/auxiliary tiebreaker (already explored — treat as noisy, not primary).
- Compute: local **RTX 4090** (Ubuntu) for dev/inference; **RunPod A100 (EU-RO-1)** for any
  batch-heavy jobs; MacBook drives remotely via Tailscale.
- Backbone for Track B: frozen **V-JEPA 2** (temporal). DINOv2 acceptable as a frame-level
  substrate for fast iteration / ablation only.

> **Note (Appendix A1):** the split into `visualstack` + `momentscan` supersedes the
> single-monorepo assumption above. The PoC runs on the split.

## 8. Telemetry hooks (future-proof now, wire later)
Even with no sales loop, log per served candidate: `clip_id`, `track_id`, `rider_role`,
candidate frame/segment ids, track (A/B), feature scores, the model's pick + alternatives,
timestamp. When the product later offers buy/choose/skip, **this schema becomes the free,
label-free reward signal that closes the self-improvement loop.** Design the log now; the
loop attaches later without a schema migration.

## 9. Open questions for the human (surface, do not guess)
- ~~Exact clip length / fps / resolution and storage location of the daily videos.~~ → A3.
- ~~Seating geometry / camera framing~~ / typical max persons per clip. → A3.
- ~~Which `visualbind` signals stay reliable under heavy occlusion~~ → A3 (retest pending).
- ~~Privacy / retention policy for face video.~~ → A3 (no constraint for PoC).
- V-JEPA 2 checkpoint/variant available, and its **commercial-use license** terms. *(open — Phase 4)*

---

# Appendix — Session decisions (2026-06-08)

Decisions made jointly while reorienting momentscan onto this PoC. These **refine or
supersede** parts of the body above; where they conflict, the appendix wins.

## A0. Reorientation
- The momentscan rebuild is **reoriented to be this PoC** (not a separate effort). The
  rebuild's first vertical slice = Track A `Profile`+`Highlight` + eval harness + telemetry.
- **`Distribution` unification.** momentscan's contract object is `Distribution`
  (`merge` + `center` / `spread` / `distance`), parametrized by **feature space**. Track A
  feeds it 45D specialist signals; Track B feeds it V-JEPA embeddings. *Same abstraction,
  same eval harness, differing only in features* → the "directly comparable" of §2 is
  literally one code path with a swapped feature source.
- **Readings narrowed for PoC.** Only two readings matter now:
  `center` → **Profile** (identity reference to narrow candidates), and
  `distance` as **conditional residual** → **Highlight**. `spread` (diversity),
  appearance/shape/category Distributions, and the full selector surface are **deferred
  past the decision gate**.

## A1. Location
- PoC runs on the **`visualstack` + `momentscan` split**, NOT the `reportrait` monorepo.
- Distribution math lives in **visualstack**; `personmemory`'s Welford/Mahalanobis is
  **absorbed as the reference implementation** of `Distribution` (dedup). The `signal`
  Distribution (47 tests) is reused.
- **momentscan = Track A/B selection + eval harness + telemetry** on top of visualstack.

## A2. Subject attribution — depth is the primary cut (refines §5)
- **Correction:** an earlier draft of this appendix conflated *height* with *depth* and
  wrongly demoted depth. They are different axes:
  - **Depth (distance-to-camera) = PRIMARY, near-valid in practice.** Seating is fixed
    geometry: the **front seat (main) is closer to the camera, the back seat (auxiliary) is
    farther**. Age-independent; held up well in prior testing.
  - **Height / vertical position / absolute face size does NOT generalize** — children may
    sit in either seat, so a small or low face does *not* imply the back seat. This (not
    depth) is what fails.
- So: **main vs auxiliary = depth (front/back), primary.** The camera sits at the front
  rider's front-right-bottom (A3), so the main rider is the nearer face.
- **Corroborating signals (to absorb a noisy per-frame depth estimate):** the auxiliary
  (back) rider is also **more occluded / intermittent** (hidden behind the front rider,
  visible only when poking out) and the main rider's track is **more persistent / dominant**.
  Use these to *stabilize* the depth cut, not to replace it.
- **Staff / bystander rejection** unchanged: scene-phase persistence (do not persist into
  the ride/descent phase) + roadside position.
- This **upgrades depth from §5's "tiebreaker" and overrides §7's "not primary" aside**:
  depth is the primary main/aux discriminator; corroborate to handle estimator noise.

## A3. Data realities (answers to §9)
- **Storage**: pool = `~/Videos/reaction`; eval seed set = `~/Videos/reaction_test`.
- **Camera**: no standard calibration. Mounted at the customer's **front-right-bottom,
  looking slightly up** — off-axis frontal. ⇒ there is no *absolute* "frontal"; the
  **standard pose = the center of what this camera sees most** (the `center` reading IS the
  empirical frontal). No calibration needed.
- **Max 2 riders.** Staff faces are detected at clip start and intermittently at the
  roadside.
- **Rear rider** mostly occluded behind the front rider's back; face visible only
  occasionally.
- **Privacy**: no constraint for the PoC — proceed.

## A4. Occlusion handling — supersedes "signal-dropout → occlusion" (legacy)
- The legacy approach (predict occlusion from missing signals) was **unstable** and is
  **dropped**. Do **not** build an occlusion detector.
- Instead, occlusion is **absorbed by the Distribution's robust centroid**
  (trimmed mean / median): occluded / missing-signal frames are **down-weighted samples**,
  not special cases.
- **This also kills the legacy `n=0` bug** (per-subject Welford produced empty stats
  because "any-NaN-column ⇒ skip whole frame"). With robust aggregation, a missing signal is
  a down-weighted sample, not a full-frame skip — both fragilities die with one design move.
