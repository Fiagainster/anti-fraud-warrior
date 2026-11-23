import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_maps import load, sector_edges, MAPS
from collections import defaultdict

name = sys.argv[1] if len(sys.argv) > 1 else "FZ02"
secs = [int(x) for x in sys.argv[2:]] or [2]
w = load(MAPS / (name + ".wad"))
print("verts:", len(w["verts"]))
for sec in secs:
    print("\n== sector %d  f/c=%d/%d 光%d ==" % (sec, w["sectors"][sec]["floor"],
                                                 w["sectors"][sec]["ceil"],
                                                 w["sectors"][sec]["light"]))
    edges = sector_edges(w, sec)
    indeg, outdeg = defaultdict(int), defaultdict(int)
    for a, b, i, s in edges:
        outdeg[a] += 1
        indeg[b] += 1
    for v in sorted(set(indeg) | set(outdeg)):
        if indeg[v] != outdeg[v]:
            print("  缺口顶点 v%d @%s  in=%d out=%d"
                  % (v, w["verts"][v], indeg[v], outdeg[v]))
            for a, b, i, s in edges:
                if a == v or b == v:
                    ln = w["lines"][i]
                    fs = w["sides"][ln["front"]]["sec"] if ln["front"] is not None else None
                    bs = w["sides"][ln["back"]]["sec"] if ln["back"] is not None else None
                    print("      line %d %s->%s side=%s f=%s b=%s sp=%d"
                          % (i, w["verts"][a], w["verts"][b], s, fs, bs, ln["special"]))
    # 也打印所有重复起点/多条出边的顶点
    print("  -- 所有边 --")
    for a, b, i, s in sorted(edges, key=lambda e: (e[0], e[1])):
        print("     %s -> %s  (line %d, %s)" % (w["verts"][a], w["verts"][b], i, s))
