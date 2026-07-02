"""Signal extractors - one research SPECIALTY per module, isolatable on demand.

``ls extraction/`` = the running signal-analysis list (the /dev principle: the
tree itself answers "what signal analyses exist" without running a command):
detect(face+reid) parse(face-parsing/skin) fashion(FashionCLIP) headpose(6DRepNet)
features(HSEmotion+AU+DPR-SH 46d) scene(DINO).

Each module is a signal-processing specialty a dedicated expert could own and
deepen. The isolation LADDER (legacy vpx-plugins intent, kept without the
machinery - boundaries always, isolation paid when needed):
  (1) in-app module        free            parse fashion headpose
  (2) workspace package    dep conflicts   features scene -> plugins/features-specialist45d
  (3) plugin + bus         warm/realtime   detect landmarks -> visualstack plugins (visualpath DAG)
landmarks is the one node with NO module here - already at rung (3), produced by
the ingest machinery via the visualstack face-landmarks plugin.

Membership test: "is this a signal-extraction specialty (a model observing)?"
Deliberately elsewhere: subjects/ = what the signals attach TO (attribute
tubelets crops - the subject contract); ingest/daemon = machinery (package
root); stitch = identity-domain policy (domains/).
"""
