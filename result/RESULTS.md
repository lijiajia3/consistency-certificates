# Consistency Certificates — 实验结果汇总

免金标、单次解码、可证明 sound 的黑箱 LLM 文档级 IE 错误下界证书。
数据 Re-DocRED dev（297 篇, 4 valid 模型公共集），模型 Qwen2.5-{7B,14B,32B,72B} + DeepSeek-V3，全程黑箱 JSON-mode T=0。

## 核心结果

| 模型 | validJSON | 触发率 | soundness（可核违反→真错） | 定理逐篇 | 可检测类 |
|---|---|---|---|---|---|
| Qwen2.5-7B | 5% | — | — | 100% | — |
| Qwen2.5-14B | 99% | 66% | 636/636 = **100%** | 100% | 23% |
| Qwen2.5-32B | 100% | 66% | 548/548 = **100%** | 100% | 23% |
| Qwen2.5-72B | 100% | 72% | 699/699 = **100%** | 100% | 22% |
| DeepSeek-V3 | 100% | 73% | 698/698 = **100%** | 100% | 24% |

- **soundness 全体 2929/2929 = 100%，零假阳**（经验签名 2581 + 定义硬签名 348）。
- **定理**（#err ≥ 顶点覆盖 ≥ 匹配）：代码 2000 图压力测试 + 真实数据逐篇 100% 成立。
- **稳健性**：hold-out（不相交文档签名）99.8%（3537/3544）；schema-only（零语料 Wikidata 语义）98.8%（3134/3171）。
- **弱模型崩塌**：7B 仅 5% 产出合法结构（退化重复）。
- **E5 self-consistency 基线**：部署 T=0 抽取的 99 个认证错误中 **21% 自洽**（≥3/5 高温解码复现）→ resampling 漏检、证书抓到。
- **E6 triage**：逐篇下界 vs 真错 Spearman ρ=0.26–0.31；top-10 文档占下界总和 12–13%（覆盖真错 4–5%）。
- **跨架构对照**：GLM-4-32B 651/651 = 100%（170 篇，供应商限流）。

## 数据说明

DeepSeek-V3 的抽取已补全至全部 300 篇 dev 文档（原缺 106 篇），其中 299 篇合法输出、1 篇（doc 295）输出为空。
论文主表在 297 篇公共集上计算（排除 Qwen2.5-14B 报错的 doc 147/176 与 V3 空输出的 doc 295）。

## 诚实定位

- 组合下界（VC ≤ 错误数）是**数据库修复的经典结果**（Bertossi 2011；PASS 2601.20157），**非新定理**。
- 贡献 = 把该证书**迁移到黑箱 LLM IE 可靠性认证** + 跨模型经验刻画 + 可检测类 + 与 self-consistency 互补。适配 **IEEE Access**（判 soundness，不判创新度）。
- 与 SH-ETRs 等"类型约束涨 F1"卡死区别：**免训练、免金标、黑箱认证**。

## 复现

```bash
python3 code/certificate.py            # 定理单元+压力测试
python3 code/run_extractions.py        # 6模型×300篇 缓存抽取(需 ~/.siliconflow_key)
python3 code/analyze.py                # 主表(E2/E3/E7)
python3 code/ablation_holdout.py       # hold-out 99.8%
python3 code/ablation_schema.py        # schema-only 98.8%
python3 code/analyze_glm.py            # GLM 651/651
python3 code/run_resample.py           # E5 K=5 高温解码
python3 code/analyze_resample.py       # E5 分析 (21%)
python3 code/analyze_triage.py         # E6
python3 code/make_figures_pub.py       # 投稿级图 F1–F11
cd paper && pdflatex main.tex          # 论文
```
