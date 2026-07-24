# Consistency Certificates — 实验结果汇总

免金标、单次解码、可证明 sound 的黑箱 LLM 文档级 IE 错误下界证书。
数据 Re-DocRED dev（194 篇, 4 valid 模型公共集），模型 Qwen2.5-{7B,14B,32B,72B} + DeepSeek-V3，全程黑箱 JSON-mode T=0。

## 核心结果

| 模型 | validJSON | 触发率 | soundness（可核违反→真错） | 定理逐篇 | 可检测类 |
|---|---|---|---|---|---|
| Qwen2.5-7B | 5% | — | — | 100% | — |
| Qwen2.5-14B | 99% | 64% | 386/386 = **100%** | 100% | 22% |
| Qwen2.5-32B | 100% | 65% | 372/372 = **100%** | 100% | 23% |
| Qwen2.5-72B | 100% | 71% | 431/431 = **100%** | 100% | 21% |
| DeepSeek-V3 | 100% | 71% | 469/469 = **100%** | 100% | 24% |

- **soundness 全体 1904/1904 = 100%，零假阳**（经验签名 1658 + 定义硬签名 246）。
- **定理**（#err ≥ 顶点覆盖 ≥ 匹配）：代码 2000 图压力测试 + 真实数据逐篇 100% 成立。
- **弱模型崩塌**：7B 仅 5% 产出合法结构（退化重复）。
- **E5 self-consistency 基线**：部署 T=0 抽取的 99 个认证错误中 **21% 自洽**（≥3/5 高温解码复现）→ resampling 漏检、证书抓到。
- **E6 triage**：逐篇下界 vs 真错 Spearman ρ=0.25–0.40（诚实中等）。

## 诚实定位
- 组合下界（VC ≤ 错误数）是**数据库修复的经典结果**（Bertossi 2011；PASS 2601.20157），**非新定理**。
- 贡献 = 把该证书**迁移到黑箱 LLM IE 可靠性认证** + 跨模型经验刻画 + 可检测类 + 与 self-consistency 互补。适配 **IEEE Access**（判 soundness，不判创新度）。
- 与 SH-ETRs 等"类型约束涨 F1"卡死区别：**免训练、免金标、黑箱认证**。

## 复现
```bash
python3 certificate.py            # 定理单元+压力测试
python3 run_extractions.py        # 5模型×100篇 缓存抽取(需 ~/.siliconflow_key)
python3 analyze.py                # 主表(E2/E3/E7)
python3 run_resample.py           # E5 K=5 高温解码
python3 analyze_resample.py       # E5 分析
python3 analyze_triage.py         # E6
python3 make_figures.py           # 图
cd paper && pdflatex main.tex     # 论文
```
