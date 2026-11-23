## v1.0 — 271 个样本 / 8 类手势 / 4 个批次

2026-11-13 自采，TI AWR1642 + DCA1000，77 GHz，2T4R。

### 附件

| 文件 | 样本数 | 大小 |
|---|---|---|
| `s1_original.fmcwb` | 120（LL / RR / FF / BB / AA / CC） | 794 MiB |
| `s2_far.fmcwb` | 81（约 1 m 远距） | 530 MiB |
| `s3_updown.fmcwb` | 40（UU / DD） | 259 MiB |
| `s4_more_ffbb.fmcwb` | 30（FF / BB） | 212 MiB |

原始 4.23 GiB，无损压缩至 1.75 GiB。

### 使用

```bash
pip install numpy
python fmcwpack.py verify s1_original.fmcwb
python fmcwpack.py unpack s1_original.fmcwb data/
```

解包后得到定长 16 MiB 原始 `.bin`，可直接输入课程提供的 `bin2mat`。
SHA-256 清单见仓库 `manifest.csv`。

### 许可

数据 CC BY-NC-SA 4.0；解包器 MIT。
