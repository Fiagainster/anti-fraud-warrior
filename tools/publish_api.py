#!/usr/bin/env python3
"""One-off publisher: upload the current HEAD tree through api.github.com.

Used because this network blocks github.com (git push) but allows
api.github.com. Creates blobs -> tree -> commit -> ref, i.e. the same
object graph a push would create, squashed into one initial commit.
"""
from __future__ import annotations

import base64
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = "Fiagainster/anti-fraud-warrior"
ROOT = Path(__file__).resolve().parents[1]


def api(method: str, path: str, payload=None):
    cmd = ["gh", "api", "--method", method, f"repos/{REPO}/{path}"]
    if payload is not None:
        cmd += ["--input", "-"]
    r = subprocess.run(cmd, input=json.dumps(payload).encode() if payload else None,
                       capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"{method} {path} failed: {r.stderr.decode('utf-8','replace')[:800]}")
    return json.loads(r.stdout.decode("utf-8"))


def tracked() -> list[tuple[str, str]]:
    out = subprocess.run(["git", "-C", str(ROOT), "-c", "core.quotePath=false", "ls-files", "-s"],
                         capture_output=True, check=True).stdout.decode("utf-8", "replace")
    items = []
    for line in out.splitlines():
        meta, path = line.split("\t", 1)
        mode, _sha, _stage = meta.split()
        items.append((mode, path))
    return items


def ensure_initialized() -> str:
    """An empty repository rejects git/blobs with 409; seed it with one
    tiny commit through the Contents API first."""
    try:
        api("GET", "contents/.init")
        return "exists"
    except RuntimeError:
        pass
    payload = {
        "message": "init: 初始化仓库",
        "content": base64.b64encode(b"anti-fraud-warrior" + bytes([10])).decode("ascii"),
    }
    out = api("PUT", "contents/.init", payload)
    sha = out["commit"]["sha"]
    print("initialized repository with seed commit", sha)
    return sha

def main() -> int:
    seed = ensure_initialized()
    files = tracked()
    print(f"uploading {len(files)} files to {REPO}")

    def make_blob(item):
        mode, path = item
        raw = (ROOT / path).read_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        out = api("POST", "git/blobs", {"content": b64, "encoding": "base64"})
        return {"path": path, "mode": mode, "type": "blob", "sha": out["sha"]}

    entries = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for i, entry in enumerate(pool.map(make_blob, files), 1):
            entries.append(entry)
            if i % 20 == 0 or i == len(files):
                print(f"  blobs {i}/{len(files)}")
    entries.sort(key=lambda e: e["path"])

    tree = api("POST", "git/trees", {"tree": entries})
    print("tree:", tree["sha"])

    msg = subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--pretty=%B"],
                         capture_output=True, check=True).stdout.decode("utf-8", "replace").strip()
    message = ("初始开源：反诈战士 · 三章反诈 FPS 演示\n\n"
               "内容层（ZScript/MAPINFO/字体图集生成）、地图生成器、自动化接管、"
               "团队协作文档与交付打包。\n\n"
               f"本地历史提示：导入的提交为 {msg.splitlines()[0] if msg else 'HEAD'}")
    parents = [] if seed == "exists" else [seed]
    commit = api("POST", "git/commits", {"message": message, "tree": tree["sha"],
                                          "parents": parents})
    print("commit:", commit["sha"])

    try:
        api("POST", "git/refs", {"ref": "refs/heads/main", "sha": commit["sha"]})
        print("ref created: refs/heads/main")
    except RuntimeError:
        api("PATCH", "git/refs/heads/main", {"sha": commit["sha"], "force": True})
        print("ref updated: refs/heads/main")

    verify = api("GET", f"git/trees/{commit['sha']}?recursive=1")
    print("remote tree entries:", len(verify.get("tree", [])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
