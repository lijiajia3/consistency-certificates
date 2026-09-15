# SciERC source and integrity

The normalized JSONL splits in this directory are the official processed SciERC data published by the dataset authors:

- Dataset page: https://nlp.cs.washington.edu/sciIE/
- Processed archive: https://nlp.cs.washington.edu/sciIE/data/sciERC_processed.tar.gz
- Paper: Yi Luan, Luheng He, Mari Ostendorf, and Hannaneh Hajishirzi, "Multi-Task Identification of Entities, Relations, and Coreference for Scientific Knowledge Graph Construction," EMNLP 2018, https://aclanthology.org/D18-1360/

The files use one JSON document per line. Their SHA-256 digests are:

```text
04970819bd215fce8c60b3a64fccca15388b49eab2010bdc5f6d322b463568c3  train.json
61f21b224129e580a654b036ee6fffeeb1a0311f1009a38ea931c13612db040e  dev.json
7424da64e6214a90e39b09e47a74b3ded57dde86b4a7f848b3625d2c8ecdfbe1  test.json
```

SciERC contains 500 scientific abstracts with six entity types and seven relation types. The official split contains 350 train, 50 development, and 100 test documents. Training annotations are used only to derive permissive type signatures; external validation is performed on development and test documents.
