#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fmcwpack.py — FMCW raw-ADC 无损容器。

原创实现，独立于任何课程/上游信号处理代码。仅依赖 numpy + 标准库 lzma。

容器格式 FMCWBIN1
-----------------
  magic         8 B    b"FMCWBIN1"
  version       u32 LE
  manifest_len  u32 LE
  manifest      UTF-8 JSON（文件清单、量化位数、双 SHA-256）
  payload       n × (u64 LE 长度 + LZMA 流)

变换（整数、双射，解码可逐字节还原）
-----------------------------------
一个 16 MiB 文件 = 2,097,152 组 × 4 个 int16 = [I_A, I_B, Q_A, Q_B]。
文件线性顺序是 (chirp, RX, ADC)：每 chirp 有 4×256/2 = 512 组，
同一 TX 的相邻 chirp 在组轴上相距 2×512 = **1024 组**。
所以复数 lag-2 差分等价于步长 1024 的组差分：

    forward:  r[:1024] = g[:1024];  r[1024:] = g[1024:] - g[:-1024]
    inverse:  g = cumsum(r.reshape(-1, 1024, 4), axis=0).reshape(-1, 4)

量化（可选，--quant k）
-----------------------
    q = ((x + 2^(k-1)) >> k) << k          k=0 表示不量化
量化只影响发布数据，manifest 同时记录量化前/后的 SHA-256。

用法
----
    python fmcwpack.py pack   out.fmcwb --quant 3 --jobs 8 FILE...
    python fmcwpack.py unpack in.fmcwb OUTDIR
    python fmcwpack.py verify in.fmcwb
    python fmcwpack.py info   in.fmcwb
"""
from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import os
import struct
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

MAGIC = b"FMCWBIN1"
VERSION = 1
FILE_BYTES = 16_777_216
GROUPS = FILE_BYTES // 8          # 2,097,152
STRIDE = 1024                     # 同 TX 相邻 chirp 的组跨度
ROWS = GROUPS // STRIDE           # 2048
PRESET = 9 | lzma.PRESET_EXTREME


# ---------------------------------------------------------------- 核心变换
def quantize(raw: np.ndarray, k: int) -> np.ndarray:
    if k <= 0:
        return raw.copy()
    x = raw.astype(np.int32)
    x = ((x + (1 << (k - 1))) >> k) << k
    return np.clip(x, -32768, 32767).astype(np.int16)


def forward(q: np.ndarray) -> np.ndarray:
    """步长 1024 的组差分（= 同 TX 相邻 chirp 的复数 lag-2）。"""
    g = q.reshape(GROUPS, 4)
    r = g.astype(np.int32)
    r[STRIDE:] = g[STRIDE:].astype(np.int32) - g[:-STRIDE]
    lo, hi = int(r.min()), int(r.max())
    if lo < -32768 or hi > 32767:
        raise ValueError(f"差分溢出 int16: [{lo}, {hi}]")
    return r.astype(np.int16).reshape(-1)


def inverse(resid: np.ndarray) -> np.ndarray:
    """按步长 1024 分组累加还原。"""
    g = np.cumsum(resid.reshape(ROWS, STRIDE, 4), axis=0, dtype=np.int32)
    if g.min() < -32768 or g.max() > 32767:
        raise ValueError("累加溢出 int16")
    return g.reshape(GROUPS, 4).astype(np.int16).reshape(-1)


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------- 打包
def _pack_one(args):
    path, root, k = args
    raw = np.fromfile(path, dtype=np.int16)
    if raw.size * 2 != FILE_BYTES:
        raise ValueError(f"{path}: 大小 {raw.size*2} != {FILE_BYTES}")
    sha_cap = sha(raw.tobytes())
    q = quantize(raw, k)
    sha_pub = sha(q.tobytes())
    blob = lzma.compress(forward(q).tobytes(), preset=PRESET)
    rel = os.path.relpath(path, root).replace(os.sep, "/")
    parts = Path(rel).parts
    entry = {
        "path": rel,
        "size": int(q.nbytes),
        "sha256": sha_pub,
        "sha256_captured": sha_cap,
        "session": parts[0] if len(parts) > 1 else "",
        "label": parts[1] if len(parts) > 2 else "",
    }
    return entry, blob


def cmd_pack(a):
    files = sorted(a.files)
    root = a.root or os.path.commonpath([os.path.dirname(os.path.abspath(p)) for p in files])
    t0 = time.time()
    print(f"打包 {len(files)} 个文件  quant={a.quant}  jobs={a.jobs}  root={root}")
    tasks = [(os.path.abspath(p), root, a.quant) for p in files]
    results = []
    with Pool(a.jobs) as pool:
        for i, (entry, blob) in enumerate(pool.imap(_pack_one, tasks, chunksize=1), 1):
            results.append((entry, blob))
            if i % 10 == 0 or i == len(tasks):
                print(f"  {i}/{len(tasks)}  {time.time()-t0:.0f}s  "
                      f"累计 {sum(len(b) for _, b in results)/1e6:.1f} MB", flush=True)

    manifest = {
        "format": "FMCWBIN1",
        "version": VERSION,
        "layout": {"file_bytes": FILE_BYTES, "groups": GROUPS,
                   "group": ["I_A", "I_B", "Q_A", "Q_B"],
                   "stride_groups": STRIDE, "rows": ROWS},
        "transform": "r[:1024]=g[:1024]; r[1024:]=g[1024:]-g[:-1024] "
                     "(complex lag-2 along chirp, same TX)",
        "codec": "lzma preset 9|EXTREME, one stream per file",
        "quant_bits": a.quant,
        "quant_rule": "q = ((x + 2^(k-1)) >> k) << k" if a.quant else "none",
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "files": [e for e, _ in results],
    }
    mb = json.dumps(manifest, ensure_ascii=False).encode("utf-8")
    with open(a.out, "wb") as f:
        f.write(MAGIC)
        f.write(struct.pack("<II", VERSION, len(mb)))
        f.write(mb)
        for _, blob in results:
            f.write(struct.pack("<Q", len(blob)))
            f.write(blob)
    total = sum(e["size"] for e, _ in results)
    print(f"完成: {a.out}  {os.path.getsize(a.out)/1e6:.1f} MB / "
          f"{total/1e6:.1f} MB = {total/os.path.getsize(a.out):.3f}x  "
          f"{time.time()-t0:.0f}s")


# ---------------------------------------------------------------- 读取/校验
def iter_archive(path):
    with open(path, "rb") as f:
        if f.read(8) != MAGIC:
            raise ValueError("不是 FMCWBIN1 容器")
        ver, n = struct.unpack("<II", f.read(8))
        if ver != VERSION:
            raise ValueError(f"不支持的版本 {ver}")
        manifest = json.loads(f.read(n).decode("utf-8"))
        for e in manifest["files"]:
            ln = struct.unpack("<Q", f.read(8))[0]
            yield manifest, e, f.read(ln)


def restore(blob: bytes) -> bytes:
    resid = np.frombuffer(lzma.decompress(blob), dtype=np.int16)
    return inverse(resid).tobytes()


def cmd_verify(a):
    ok = True
    n = 0
    for manifest, e, blob in iter_archive(a.archive):
        raw = restore(blob)
        good = len(raw) == e["size"] and sha(raw) == e["sha256"]
        ok &= good
        n += 1
        if not good:
            print(f"  BAD {e['path']}")
    print(f"{n} 个文件: {'ALL OK' if ok else 'FAILED'}")
    return 0 if ok else 1


def cmd_unpack(a):
    for manifest, e, blob in iter_archive(a.archive):
        dst = Path(a.outdir) / e["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        raw = restore(blob)
        if len(raw) != e["size"] or sha(raw) != e["sha256"]:
            raise RuntimeError(f"校验失败: {e['path']}")
        dst.write_bytes(raw)
    print(f"已解包到 {a.outdir}")


def cmd_info(a):
    for manifest, _, _ in iter_archive(a.archive):
        print(json.dumps({k: v for k, v in manifest.items() if k != "files"},
                         ensure_ascii=False, indent=2))
        from collections import Counter
        c = Counter(e["session"] for e in manifest["files"])
        print("文件数:", len(manifest["files"]), " 分组:", dict(c))
        print("量化位数:", manifest["quant_bits"])
        return


def main():
    ap = argparse.ArgumentParser(description="FMCW raw-ADC 无损容器")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("pack", help="打包")
    p.add_argument("out")
    p.add_argument("files", nargs="+")
    p.add_argument("--quant", type=int, default=0, help="丢弃的低位数 (0=不量化)")
    p.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    p.add_argument("--root", default=None)
    p.set_defaults(func=cmd_pack)

    p = sub.add_parser("unpack", help="解包")
    p.add_argument("archive")
    p.add_argument("outdir")
    p.set_defaults(func=cmd_unpack)

    p = sub.add_parser("verify", help="只校验不落盘")
    p.add_argument("archive")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("info", help="查看 manifest")
    p.add_argument("archive")
    p.set_defaults(func=cmd_info)

    a = ap.parse_args()
    sys.exit(a.func(a) or 0)


if __name__ == "__main__":
    main()
