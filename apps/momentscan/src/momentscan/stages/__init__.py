"""L0-L1 extraction stages - every DAG node has a module here (declared DAG: analyzers.py).

Two families share the layer:
  in-app         transforms/adapters that run in the core venv (detect ingest daemon
                 attribute tubelets crops parse fashion headpose stitch)
  plugin-backed  thin adapters (features.py scene.py) whose model BACKEND lives in
                 plugins/features-specialist45d - an isolated workspace package (heavy
                 model deps + the FeatureSource swap port + a service-worker boundary).
                 Same relation as the visualstack plugins behind detect/landmarks.
"""
