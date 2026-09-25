# Consistency Certificates：修订实验结果

本轮修订将证书的数学对象纠正为“冲突超图”：类型签名违反对应三元超边
`{头实体类型项, 尾实体类型项, 关系断言项}`。错误项构成超图的 hitting set，最大顶点不相交
超边打包数给出条件错误下界。实现采用精确分支定界，并与 500 个随机小超图的穷举结果逐一核对。

## Re-DocRED 主结果

297 篇公共文档、四个可用主模型、经验签名：

| 模型 | 触发文档 | 冲突超边 | 精确下界总和 | 回溯验证 | 可检测的已发出错误 |
|---|---:|---:|---:|---:|---:|
| Qwen2.5-14B | 195/297 | 667 | 273 | 632/632 | 24.82% |
| Qwen2.5-32B | 196/297 | 573 | 247 | 540/540 | 24.40% |
| Qwen2.5-72B | 214/297 | 774 | 346 | 684/684 | 24.11% |
| DeepSeek-V3 | 218/297 | 755 | 297 | 691/691 | 25.23% |

- 四个主模型的精确下界合计为 **1,163**（273 + 247 + 346 + 297）。
- 经验签名 2547/2547，但其签名库与验证数据共享注释来源，因此仅作为构造对齐的诊断结果。
- 定义签名 340/340，单侧 95% 假阳性率上界为 **0.88%**。
- 二折不相交文档签名：**3495/3501 = 99.8%**，exact 95% CI 99.63–99.94%。
- 人工指定、且不使用语料统计的 schema 签名：**3076/3122 = 98.5%**，exact 95% CI 98.04–98.92%。
- 保守的 cluster-ID 对齐使不可核验违反从旧字符串启发式的 188 个增加到 222 个。
- 精确下界与真错误数的 Spearman 相关为 0.327–0.369；文档 tightness 中位数为 0.080–0.083。
- 5%、10%、20% 审核预算下，按证书排序平均每篇发现 12.63、12.25、11.45 个错误；
  跨模型分歧基线为 10.20、10.07、10.82，随机基线为 10.37、10.38、10.37。
- Qwen2.5-32B 的 102 个唯一、证书可见且金标可核验的错误项中，28 个在五次随机解码中至少复现三次（27.5%）。
- 五模型严格完整性检查均为 50/50 文档、每文档 5 次随机解码。稳定错误项比例分别为
  Qwen2.5-14B 31/158（19.6%）、Qwen2.5-32B 28/102（27.5%）、
  Qwen2.5-72B 74/168（44.0%）、DeepSeek-V3 80/158（50.6%）、GLM-4-32B
  54/223（24.2%）；完整 0/5--5/5 分布见 `result/revision/self_consistency_by_model.csv`。
- GLM-4-32B 跨架构对照：300/300 篇有效，精确下界合计 395，1085/1085 个可核验违反成立，
  逐文档 theorem 300/300 通过；唯一反复触发长度上限的文档使用了不含 gold 信息的防重复输出 fallback。

## 独立语料 SciERC

签名只由 SciERC 350 篇训练文档构造，在全部 50 篇开发集和 100 篇测试集上冻结评估：

- 150/150 文档有效，109 篇触发；
- 134/134 个可核验违反成立，exact 95% CI 97.28–100%；
- 127 个违反因端点不能保守对齐而不进入回溯验证分母；
- runtime 下界 159，gold-checkable 下界 93；
- 150/150 篇均满足“可核验下界不超过 gold-verifiable 已发出错误数”。

## 复现

```bash
python3 code/certificate.py
python3 code/analyze.py
python3 code/ablation_holdout.py
python3 code/ablation_schema.py
python3 code/analyze_glm.py
python3 code/analyze_revision.py
python3 code/analyze_resample.py --all-models --documents 50 --samples 5 --require-complete
python3 code/analyze_scierc.py --require-complete
python3 code/make_figures_pub.py
python3 code/reproduce_all.py
```

完整机器可读结果位于 `result/revision/` 和 `result/scierc/`。
