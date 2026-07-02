"""L0-L1 extraction - the ANALYSIS NODES of the clip DAG, one module per
node (declared DAG: analyzers.py): detect attribute tubelets crops parse fashion
headpose features scene.

  - landmarks is the one node with NO module here: the frame-grain ingest
    machinery (ingest.py/daemon.py at the package root) produces it via the
    visualstack face-landmarks plugin.
  - features.py / scene.py are thin adapters whose model BACKEND lives in
    plugins/features-specialist45d (isolated workspace package: heavy model deps
    + FeatureSource swap port + service-worker boundary) - the same relation as
    the visualstack plugins behind detect/landmarks.

Deliberately NOT here: ingest.py / daemon.py = frame-grain runtime machinery
(pipeline.py's siblings, package root); stitch.py = identity-domain algorithm
(domains/). extraction/ answers "what analysis runs", not "what machinery runs it".
"""
