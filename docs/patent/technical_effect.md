# Technical effects and evidence

The implemented design targets less re-evaluation through indexed delta processing, lower assignment wastage through global allocation, and consistent reservation under concurrent writes. No measured technical-effect figures are available yet because the PostgreSQL container could not start in the authoring environment. Delta-vs-full-scan, optimal-vs-greedy, and import-throughput measurements must be generated and attached by executable benchmark runs. No numerical improvement is claimed here.
