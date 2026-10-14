**简体中文** | [English report](REPORT.en.md)

# 接近探测系统漂移：实验资料

2026-10-13 单台 Neptune 4 Max 的实验记录，2026-10-15 整理发布。包括升温、被回床测量打断的降温、5/8 分钟近床保持、周期参考修正，以及实际 XY 集成检查。

- [中文完整报告](REPORT.md) · [English report](REPORT.en.md)
- [原始 CSV 与 SHA256 清单](source-manifest.json) · [复算指标](summary.json)
- [离线复算和英文作图脚本](reproduce.py) · [依赖版本](requirements.txt)
- [外部来源与核查范围](sources.md)

这些数据支持本机存在与热历史相关的触发高度变化，以及周期参考改善固定位置基准一致性的观察。它们没有独立分离探针电气温漂和机械热变形，也没有证明整床绝对精度优于充分稳定后的常规测网。详细范围和限制见双语报告。

The records show thermal-history-related trigger-height changes on one printer and improved fixed-location baseline consistency with periodic references. They do not isolate sensor electrical drift from mechanical change or establish superior spatial accuracy over a well-conditioned conventional workflow. See the English report for methods and limitations.

## 英文图表 / English figures

| Figure | PNG | SVG |
|---|---|---|
| Thermal history and recorded temperatures | [PNG](figures/01-thermal-history.png) | [SVG](figures/01-thermal-history.svg) |
| Five- vs eight-minute conditioning | [PNG](figures/02-five-vs-eight-minutes.png) | [SVG](figures/02-five-vs-eight-minutes.svg) |
| Independent references and corrected residuals | [PNG](figures/03-independent-reference-correction.png) | [SVG](figures/03-independent-reference-correction.svg) |
| Metrics from the same 90 samples | [PNG](figures/04-correction-metrics.png) | [SVG](figures/04-correction-metrics.svg) |
| Real-XY integration check | [PNG](figures/05-real-xy-integration.png) | [SVG](figures/05-real-xy-integration.svg) |

所有 CSV 保留原记录，未删除有效样本。复算脚本只处理本地数据，不连接或操作打印机。
All CSV files retain the original records. The analysis script only processes local data and does not connect to or operate a printer.
