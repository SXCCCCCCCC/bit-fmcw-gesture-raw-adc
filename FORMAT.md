# `.fmcwb` 容器格式 v1

整数无损容器，由本项目独立实现，与任何上游信号处理代码无关。
依赖：numpy + Python 标准库 `lzma`。

## 1. 整体结构

```
偏移        长度        内容
0           8           magic = b"FMCWBIN1"
8           4 (u32 LE)  version = 1
12          4 (u32 LE)  manifest_len = N
16          N           manifest（UTF-8 JSON）
16+N        8 (u64 LE)  payload[0] 压缩长度 L0
24+N        L0          payload[0] LZMA 流
...         重复          每个文件一条独立流
```

## 2. Manifest

```json
{
  "format": "FMCWBIN1",
  "version": 1,
  "layout": {
    "file_bytes": 16777216,
    "groups": 2097152,
    "group": ["I_A", "I_B", "Q_A", "Q_B"],
    "stride_groups": 1024,
    "rows": 2048
  },
  "transform": "r[:1024]=g[:1024]; r[1024:]=g[1024:]-g[:-1024] (complex lag-2 along chirp, same TX)",
  "codec": "lzma preset 9|EXTREME, one stream per file",
  "quant_bits": 0,
  "quant_rule": "none",
  "created": "YYYY-MM-DD HH:MM:SS",
  "files": [
    {
      "path": "s1_original/LL/L1.bin",
      "size": 16777216,
      "sha256": "...",
      "sha256_captured": "...",
      "session": "s1_original",
      "label": "LL"
    }
  ]
}
```

- `sha256`：**发布版**文件的哈希（解包后应完全一致）。
- `sha256_captured`：采集原始文件的哈希。本发布版未量化，两者相同；保留该字段用于将来发布量化版时追溯。
- `quant_bits=0` 表示未量化。

## 3. 数据布局

每个文件是 8,388,608 个 int16（小端），线性顺序 **(chirp, RX, ADC)**：

```
32 帧 × 64 chirp/TX × 2 TX × 4 RX × 256 ADC = 4,194,304 个复数点
```

每 4 个 int16 一组：

```
g = [I_A, I_B, Q_A, Q_B]
A = I_A + j Q_A
B = I_B + j Q_B
```

共 `2,097,152` 组。

同一 TX 的相邻 chirp 在组轴上相距 **1024 组**（= 2 chirp × 4 RX × 256 ADC / 2 复数每组）。

## 4. 可逆变换

编码（`g` 为 `(2097152, 4)` 的 int16 组矩阵）：

```python
r = g.astype(np.int32)
r[1024:] = g[1024:].astype(np.int32) - g[:-1024]
r = r.astype(np.int16)          # 差值必须落在 int16 内
```

解码：

```python
g = np.cumsum(r.reshape(2048, 1024, 4), axis=0, dtype=np.int32)
g = g.reshape(2097152, 4).astype(np.int16)
```

这两步在整数上是严格互逆的。`r[:1024] = g[:1024]`（前 1024 组没有可参考的上一 chirp）。

## 5. 编码

每个文件的残差 `r` 按原字节序交给 `lzma.compress(..., preset=9|PRESET_EXTREME)`，
每条流独立，长度写入 payload 头。

选择 LZMA 而不是 PPMd 是为了让解码器只依赖 Python 标准库；实测 PPMd 只能再省约 6%，
而 PPMd 的 Python 绑定存在数据相关的解码错误（`L1595: Corrupted input data`），不采用。

## 6. 参考解码器

```python
import json, lzma, struct
import numpy as np

def iter_archive(path):
    with open(path, "rb") as f:
        assert f.read(8) == b"FMCWBIN1"
        ver, n = struct.unpack("<II", f.read(8))
        assert ver == 1
        manifest = json.loads(f.read(n))
        for e in manifest["files"]:
            ln = struct.unpack("<Q", f.read(8))[0]
            yield manifest, e, f.read(ln)

def restore(blob):
    r = np.frombuffer(lzma.decompress(blob), dtype=np.int16)
    g = np.cumsum(r.reshape(2048, 1024, 4), axis=0, dtype=np.int32)
    return g.reshape(2097152, 4).astype(np.int16).tobytes()
```

完整实现（含 SHA-256 校验、CLI）见 `fmcwpack.py`。

## 7. 兼容性

- 任何能读 LZMA（XZ/LZMA2 原始流）和 numpy 的环境都可以解码。
- 解码器不依赖课程代码，也不依赖模型、torch、OpenCV。
- 文件大小固定为 16 MiB；解包后直接就是课程 `bin2mat` 期待的输入。
