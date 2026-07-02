"""L2 signal domains - policy between backends and consumers (fusion, quantizers, thresholds).

Graduation rule: a signal domain earns a module here when it has >=2 backends or
fusion/quantization policy (pose 2026-07-02; identity next, with the 6D-occlusion work).
Thin single-backend readers stay in signals.py.

stitch.py = cross-track subject stitching (identity-domain cosine-merge policy,
consumed by the detect stage) - seated here ahead of the identity.py graduation.
"""
