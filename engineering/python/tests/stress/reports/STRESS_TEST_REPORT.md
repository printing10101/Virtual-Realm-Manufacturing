# 西门子标准极限压力测试报告

- 生成时间：2026-09-13 01:32:38
- Python：3.11.16
- psutil：6.1.1
- 平台：Windows-10-10.0.26200-SP0

## 结果汇总

| 测试 | 状态 | 关键指标 | 阈值 |
|------|------|----------|------|
| 并发JWT创建+验签 | PASS | avg=0.03871; p50=0.0332; p95=0.0594; p99=0.1411; max=5.604; count=5000; qps=1.843e+04; total_ms=271.3 | p99<1 |
| 并发G代码生成 | PASS | avg=2.704; p50=0.7982; p95=6.113; p99=46.84; max=158.7; count=1000; generated=1000; avg_lines=64.25 | errors<1 |
| 并发工艺规划 | PASS | avg=0.3015; p50=0.25; p95=0.4125; p99=0.9457; max=14.14; count=600; total=600 | errors<1 |
| 并发心跳调度(独立DB) | PASS | threads=10; tasks_per_thread=200; due_counts=[200,200,200,200,200...] | errors<1 |
| JWT验签吞吐量 | PASS | avg=0.03135; p50=0.0315; p95=0.0434; p99=0.0921; max=1.032; count=5000; qps=3.19e+04 | qps≥1000; p99<1 |
| G代码生成吞吐量 | PASS | avg=0.6223; p50=0.5973; p95=1.145; p99=1.334; max=1.371; count=200; qps=1607 | avg<10; p99<30 |
| 实时传感器处理吞吐量 | PASS | avg=0.005486; p50=0.0039; p95=0.0078; p99=0.0163; max=0.7126; count=1e+04; qps=1.823e+05 | p99<1 |
| 审计日志写入吞吐量 | PASS | avg=0.1307; p50=0.0608; p95=0.2027; p99=1.921; max=3.249; count=3000; qps=7652; integrity=1 | avg<5; p99<10 |
| 心跳调度add_task吞吐量 | PASS | avg=0.5555; p50=0.4543; p95=0.7182; p99=3.781; max=14.85; count=2000; qps=1800 | avg<10 |
| G代码生成浸泡(2000次) | PASS | baseline_rss_mb=880.4; final_growth_pct=0; tail_growth_pct=0; max_growth_pct=0 | growth<15 |
| 审计日志浸泡(3000条) | PASS | baseline_rss_mb=880.4; tail_growth_pct=0; max_growth_pct=0; integrity=1 | growth<15 |
| 浸泡延迟漂移(JWT) | PASS | first_p95_ms=0.03; tail_p95_ms=0.0352; drift_ratio=1.17 | drift_ratio<3 |
| 满负荷资源阈值 | PASS | cpu_avg=61; cpu_max=71.8; sys_mem_avg=96.4; sys_mem_delta=0.4; baseline_sys_mem=96.1; app_peak_rss_mb=883.6; app_baseline_rss_mb=880.4; net_avg_mbps=3.09; net_max_mbps=17.06 | cpu<90; net<50; app_rss_mb<1024; sys_mem_delta_pct<5 |
| G代码生成错误率 | PASS | error_rate_pct=0; errors=0; empty=0 | error_rate<1 |
| 心跳调度错误率 | PASS | error_rate_pct=0; errors=0 | error_rate<1 |
| 并发预算检查错误率 | PASS | error_rate_pct=0; errors=0 | error_rate<1 |
| 过载恢复(JWT) | PASS | baseline_p50_ms=0.0232; recovered_p50_ms=0.0379; recovery_ratio=1.63; burst_errors=0 | recovery_ratio<3 |
| 过载恢复(G代码生成) | PASS | baseline_p50_ms=0.787; recovered_p50_ms=0.378; recovery_ratio=0.48 | recovery_ratio<3 |

**合计：18/18 通过**
