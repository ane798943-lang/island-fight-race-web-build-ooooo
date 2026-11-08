#!/usr/bin/env python3
"""Make the class list of ifr_web.build SAFE before the engine is compiled.

Usage: check_profile.py <godot-source-dir> <profile-in.build> <required_classes.txt> <profile-out.build>

Why: if a class is switched off, every class that INHERITS from it also fails to register (this is what removed QuadMesh when
PlaneMesh was switched off). The real class tree is read from the Godot source (GDCLASS(Child, Parent) lines) and the list is
corrected automatically:
  1. a class the game needs, or any PARENT of a class the game needs, is taken off the list;
  2. a class that still has an enabled CHILD is taken off the list (repeated until nothing changes).
  0. (first) every class on the list is EXPANDED: all of its child classes are added, so a whole unused family goes at once.
What is left can only contain classes nobody needs, and no parent of anything the game needs."""
import sys, os, re, json

src, pin, req, pout = sys.argv[1:5]
parent = {}
pat = re.compile(r'\bGDCLASS\(\s*([A-Za-z0-9_]+)\s*,\s*([A-Za-z0-9_]+)\s*\)')
for root, dirs, files in os.walk(src):
    rel = os.path.relpath(root, src)
    if rel.startswith(('editor', 'tests', 'thirdparty', 'misc', 'platform' + os.sep + 'android', 'platform' + os.sep + 'ios',
                       'platform' + os.sep + 'windows', 'platform' + os.sep + 'macos', 'platform' + os.sep + 'linuxbsd',
                       'platform' + os.sep + 'visionos', '.git')):
        dirs[:] = []
        continue
    for f in files:
        if f.endswith(('.h', '.hpp', '.cpp')):
            try:
                t = open(os.path.join(root, f), errors='ignore').read()
            except Exception:
                continue
            for c, p in pat.findall(t):
                parent.setdefault(c, p)
print('classes found in the Godot source tree:', len(parent))
if len(parent) < 300:
    sys.exit('ERROR: the class tree looks incomplete - not changing anything')
children = {}
for c, p in parent.items():
    children.setdefault(p, set()).add(c)

def ancestors(c):
    out = []
    while c in parent:
        c = parent[c]
        out.append(c)
    return out

def descendants(c):
    out = set(); stack = [c]
    while stack:
        for k in children.get(stack.pop(), ()):
            if k not in out:
                out.add(k); stack.append(k)
    return out

import fnmatch
prof = json.load(open(pin))
D = set()
allc = set(parent) | set(children)
for entry in prof.get('disabled_classes', []):
    if any(ch in entry for ch in '*?'):          # a pattern such as RD* or *RD: every class of the Godot source that matches
        D |= set(fnmatch.filter(allc, entry))
    else:
        D.add(entry)
R = set(x.strip() for x in open(req) if x.strip())
removed = {}
# 0. switching a class off switches off every class that inherits from it, so list the whole family
for c in sorted(D):
    D |= descendants(c)
# 1. needed classes and their parents
for r in R:
    for a in [r] + ancestors(r):
        if a in D:
            D.discard(a); removed[a] = 'needed by the game (or a parent of %s)' % r
# 2. a class with an enabled child stays enabled
changed = True
while changed:
    changed = False
    for c in sorted(D):
        bad = [k for k in descendants(c) if k not in D]
        if bad:
            D.discard(c); removed[c] = 'has enabled child class %s' % bad[0]; changed = True
unknown = sorted(c for c in D if c not in parent)
prof['disabled_classes'] = sorted(D)
json.dump(prof, open(pout, 'w'), indent='\t')
print('disabled classes kept: %d, removed by the safety check: %d' % (len(D), len(removed)))
for c, why in sorted(removed.items()):
    print('  removed %-40s %s' % (c, why))
if unknown:
    print('note: not found in the source tree (ignored by the build):', ' '.join(unknown))
