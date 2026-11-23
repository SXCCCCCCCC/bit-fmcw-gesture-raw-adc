# FMCW 毫米波雷达手势识别 · 原始 ADC 自采数据集

本项目开源了一套基于 **TI AWR1642 + DCA1000** 采集的 **77 GHz FMCW 毫米波雷达手势原始 ADC 数据集**（共 **271** 个样本、**8 类手势**、**4 个采集批次**，采集于 2026-11-13），以及配套的 mmWave Studio 采集配置与无损压缩容器工具。

### 为什么要开源？

本数据集源于**北京理工大学《大学物理实验 II》——雷达智能手势识别**课程实验。  
该实验无需撰写传统实验报告且可抵 9 学时，但由于涉及雷达硬件配置、信号处理与深度学习全流程，整体上手门槛较高，在校内论坛上**多半差评**（[【已更新】大物实验新实验——智能雷达手势识别实验试吃体验](https://bit101.cn/gallery/9164)）。

开源本数据集旨在帮助选修该课程的同学：
1. **无设备提前演练**：在未接触实验室硬件前，提前跑通从原始 ADC 解包、雷达信号处理到深度学习训练的完整流程；
2. **参数配置参考**：提供实测可用的 `config/cf.json` 与 `config/LogFile.txt`，便于在实验课现场对照排查 mmWave Studio 配置问题；
3. **实验数据补充**：为跨距离泛化（1 m 远距）、类别扩充或自采样本不足提供干净的补充数据。

### 开源的数据是什么样？

- **纯自采数据**：全部由作者小组在实验课上独立采集，**不包含任何课程讲义、教师下发代码或教师参考数据集**。
- **原始 ADC 格式**：DCA1000 采集的定长 16 MiB 原始二进制（`.bin`），解包后可直接输入课程提供的 `newbin2mat.m` / `bin2mat.py`。
- **逐字节无损压缩**：原始 271 个文件共 **4.23 GiB**，通过自己vibe（开发中使用了 Claude Code 辅助）的 `.fmcwb` 整数差分无损容器压缩至 **1.75 GiB**（仅依赖 `numpy` + 标准库 `lzma`），解包后 SHA-256 逐字节完全一致。

---

## 1. 快速开始

> 四个 `.fmcwb` 容器不放在 git 仓库里（单个 212–794 MiB），请到
> [Releases](https://github.com/SXCCCCCCCC/bit-fmcw-gesture-raw-adc/releases)
> 下载后与 `fmcwpack.py` 放在同一目录。

```bash
pip install numpy

python fmcwpack.py info   s1_original.fmcwb       # 查看清单与元数据
python fmcwpack.py verify s1_original.fmcwb       # 仅校验 SHA-256（不写盘）
python fmcwpack.py unpack s1_original.fmcwb data/ # 解包到 data/（自动逐文件校验）
```

解包后得到 `data/s1_original/LL/L1.bin` 等文件，可直接交给课程代码处理。

---

## 2. 数据集构成

共 **8 类手势**：`LL`（左划）、`RR`（右划）、`FF`（前推）、`BB`（后移）、`UU`（上划）、`DD`（下划）、`AA`（逆时针）、`CC`（顺时针）。

| 容器文件 | 样本数 | 压缩后体积 | 类别与数量分布 | 场景说明 |
|:---|:---:|:---:|:---|:---|
| `s1_original.fmcwb` | 120 | 794 MiB | `LL` / `RR` / `FF` / `BB` / `AA` / `CC` 各 20 | 常规近距主数据集，3 人乱序混合采集 |
| `s2_far.fmcwb` | 81 | 530 MiB | `LL` 20 / `RR` 21 / `FF` 20 / `BB` 20 | **约 1 m 远距**采集，用于测试距离衰减与抗杂波 |
| `s3_updown.fmcwb` | 40 | 259 MiB | `UU` 20 / `DD` 20 | 上下手势补充 |
| `s4_more_ffbb.fmcwb` | 30 | 212 MiB | `FF` 15 / `BB` 15 | 连续采集的前后手势干净小验证集 |

- `s2_far/RR/R21.bin` 是手滑多采的一次有效样本，主分析可排除以保持每类 20 个。
- 未记录单个样本的受试者身份且采集顺序乱序；全部样本清单与双 SHA-256 校验值见 `manifest.csv`。

---

## 3. 采集参数

| 项目 | 配置值 |
|:---|:---|
| **雷达与采集** | TI AWR1642（77 GHz，2T4R）+ DCA1000（Raw 模式，2-lane LVDS，16 MiB 定长） |
| **调频斜率** | 2175 × 48.279 kHz/µs ≈ **105.0 MHz/µs** |
| **Ramp / Idle** | Ramp end = **38 µs**（扫频带宽 ≈ **4.0 GHz**），Idle time = **100 µs** |
| **ADC 采样** | **256 点 @ 10 Msps**，复数 I/Q，RX gain 30 dB |
| **通道与复用** | TX0 + TX1 全开，RX0–3 全开；chirp 在 TX0/TX1 间交替 |
| **帧结构** | **32 帧 × 64 chirp/TX**（每帧 128 个捕获 chirp），帧周期 **40 ms** |

原始配置日志见 `config/LogFile.txt` 与 `config/cf.json`（从实验机 mmWave Studio 的 `PostProc` 目录备份，时间戳与采集一致）。若课上配置遇到问题可参考；如有不同，请以当堂课下发的配置流程为准。

---

## 4. 许可与引用

- **数据**（`.fmcwb` 及解包 `.bin`）：**[CC BY-NC-SA 4.0](LICENSE-DATA.txt)**（署名—非商业性使用—相同方式共享）。课堂使用、课程作业、学位论文与非营利研究均不受「非商业性」限制；衍生数据集须以相同协议分发。
- **解包工具**（`fmcwpack.py`）：**[MIT License](LICENSE-CODE.txt)**。

```bibtex
@misc{fmcw_gesture_raw_2026,
  title  = {FMCW Radar Hand-Gesture Raw ADC Dataset (TI AWR1642 / DCA1000)},
  author = {SXCCCCCCCC and contributors},
  year   = {2026},
  note   = {271 self-collected raw ADC samples across 8 hand gestures and 4 sessions},
  url    = {https://github.com/SXCCCCCCCC/bit-fmcw-gesture-raw-adc}
}
```

---

## 附录：数据格式、物理参数与踩坑建议

### A.1 原始 `.bin` 内存布局与 Python 直接读取

每个解包后的 `.bin` 文件严格为 **16,777,216 字节**（8,388,608 个小端 `int16`），对应 `32 帧 × 64 chirp/TX × 2 TX × 4 RX × 256 ADC` 共 4,194,304 个复数点。线性顺序为 **(chirp, RX, ADC)**，每 4 个 `int16` 交织组成 2 个复数点：`[I_A, I_B, Q_A, Q_B] → A = I_A + j·Q_A, B = I_B + j·Q_B`。

除使用课程自带的 `newbin2mat.m` / `bin2mat.py` 外，也可用 NumPy 直接加载为 `(32, 64, 2, 4, 256)` 复数张量：

```python
import numpy as np

def read_dca1000_bin(path: str) -> np.ndarray:
    raw = np.fromfile(path, dtype=np.int16).reshape(-1, 4)
    iq = np.empty((raw.shape[0], 2), dtype=np.complex64)
    iq[:, 0] = raw[:, 0] + 1j * raw[:, 2]
    iq[:, 1] = raw[:, 1] + 1j * raw[:, 3]
    return iq.reshape(32, 64, 2, 4, 256)  # (Frame, Chirp_per_TX, TX, RX, ADC)
```

### A.2 雷达物理推导量速查

- **波长**：λ = c / 77 GHz ≈ **3.90 mm**
- **距离分辨率（距离门间隔）**：ΔR = (f_s / N) · c / (2 · Slope) ≈ **5.58 cm**
- **同 TX 相邻 chirp 间隔**：T_c = 2 × (100 + 38) µs = **276 µs**（PRF ≈ 3.62 kHz）
- **最大不模糊径向速度**：v_max ≈ λ · PRF / 4 ≈ **±3.53 m/s**（速度分辨率 Δv ≈ **0.11 m/s**）

### A.3 批量解包与 `.fmcwb` 容器说明

- **Windows PowerShell 一键解包全部容器**：
  ```powershell
  Get-ChildItem *.fmcwb | ForEach-Object { python fmcwpack.py unpack $_.Name data/ }
  ```
- **Linux / macOS 一键解包全部容器**：
  ```bash
  for f in *.fmcwb; do python fmcwpack.py unpack "$f" data/; done
  ```
- **容器原理**：对同 TX 相邻 chirp 做步长 1024 组的整数可逆差分（lag-2 差分），再用 `LZMA (preset 9|EXTREME)` 独立压缩每个文件。详见 [FORMAT.md](FORMAT.md)。

### A.4 实验踩坑与使用建议

1. **`s2_far`（1 m 远距）**：目标回波按 1/R⁴ 衰减，距离门外杂波占比很高；做远距分析时建议加**距离门选通**或**背景杂波抑制**，否则角度轨迹容易被杂波拉平。
2. **`s4_more_ffbb`（连续采集子集）**：5 分钟内一气呵成采完的 30 个样本，类内一致性极高，**适合当调试代码的干净小验证集，不适合当独立泛化测试集**。
3. **`s1` 的 `AA`/`CC` 与 `s3` 的 `UU`/`DD`**：画圈与上下挥动的特征与其他类别差异最明显；若做难例分析，建议重点看 `s2_far` 的 `LL`/`RR`。
4. **自采文件大小自检**：所有正常采集的 `.bin` 均为定长 **16 MiB（16,777,216 字节）**；若你在课上采出来的文件小于该大小，说明未跑满 32 帧，请先检查 mmWave Studio 配置。

