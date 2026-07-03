"""研究桥接模块（E-16 调查结论：非孤儿模块，合法保留）。

定位：
- 产品-研究之间的单向数据/能力桥梁，将生产环境中的问题、数据、实验反馈
  匿名化后输送给研究侧（论文/实验/模型迭代），不引入研究代码到生产路径。
- 被 ``app/api/v1/status.py``（研究桥接状态上报）和
  ``app/dxf/process_service.py``（DXF 处理反馈）引用，属合法产品依赖。
- ``import_guard.py`` 实现导入隔离，确保研究侧依赖（如 torch 实验工具）
  不会污染生产运行时；缺失时自动降级为 no-op。

子模块：
- data_collector / data_anonymizer : 采集并匿名化生产数据
- problem_intake / feedback_to_research : 问题与反馈上行
- experiment_runner / shadow_runner : 影子实验（不影响生产）
- research_api_client : 与外部研究服务通信
- feature_flags : 研究特性开关
"""
