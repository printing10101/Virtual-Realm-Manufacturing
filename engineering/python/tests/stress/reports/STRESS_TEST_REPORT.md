# 西门子标准极限压力测试报告

- 生成时间：2026-08-28 12:10:43
- Python：3.14.3
- psutil：7.1.3
- 平台：Windows-11-10.0.26200-SP0

## 结果汇总

| 测试 | 状态 | 关键指标 | 阈值 |
|------|------|----------|------|
| 并发JWT创建+验签 | PASS | avg=0.02735; p50=0.026; p95=0.0476; p99=0.0751; max=0.6944; count=5000; qps=2.445e+04; total_ms=204.5 | p99<1 |
| 并发G代码生成 | PASS | avg=0.5202; p50=0.4608; p95=0.7773; p99=1.028; max=16.64; count=1000; generated=1000; avg_lines=64.25 | errors<1 |
| 并发工艺规划 | PASS | avg=0.1586; p50=0.1625; p95=0.2551; p99=0.2913; max=0.3212; count=600; total=600 | errors<1 |
| 并发心跳调度(独立DB) | PASS | threads=10; tasks_per_thread=200; due_counts=[200,200,200,200,200...] | errors<1 |
| JWT验签吞吐量 | PASS | avg=0.0256; p50=0.0262; p95=0.0359; p99=0.0577; max=0.177; count=5000; qps=3.906e+04 | qps≥1000; p99<1 |
| G代码生成吞吐量 | PASS | avg=0.5152; p50=0.4845; p95=0.8601; p99=1.119; max=2.742; count=200; qps=1941 | avg<10; p99<30 |
| 实时传感器处理吞吐量 | PASS | avg=0.004704; p50=0.0049; p95=0.0063; p99=0.0174; max=0.1242; count=1e+04; qps=2.126e+05 | p99<1 |
| 审计日志写入吞吐量 | PASS | avg=0.06328; p50=0.0305; p95=0.0774; p99=1.072; max=1.734; count=3000; qps=1.58e+04; integrity=1 | avg<5; p99<10 |
| 心跳调度add_task吞吐量 | PASS | avg=0.3824; p50=0.3023; p95=0.4753; p99=3.652; max=12.78; count=2000; qps=2615 | avg<10 |
| G代码生成浸泡(2000次) | PASS | baseline_rss_mb=972; final_growth_pct=0; tail_growth_pct=0; max_growth_pct=0 | growth<15 |
| 审计日志浸泡(3000条) | PASS | baseline_rss_mb=972; tail_growth_pct=0; max_growth_pct=0; integrity=1 | growth<15 |
| 浸泡延迟漂移(JWT) | PASS | first_p95_ms=0.0426; tail_p95_ms=0.0365; drift_ratio=0.86 | drift_ratio<3 |
| 满负荷资源阈值 | PASS | cpu_avg=38.6; cpu_max=56.1; sys_mem_avg=87.2; sys_mem_delta=0.3; baseline_sys_mem=87.1; app_peak_rss_mb=974.5; app_baseline_rss_mb=972; net_avg_mbps=0.06; net_max_mbps=0.2 | cpu<90; net<50; app_rss_mb<1024; sys_mem_delta_pct<5 |
| G代码生成错误率 | PASS | error_rate_pct=0; errors=0; empty=0 | error_rate<1 |
| 心跳调度错误率 | PASS | error_rate_pct=0; errors=0 | error_rate<1 |
| 并发预算检查错误率 | PASS | error_rate_pct=0; errors=0 | error_rate<1 |
| 过载恢复(JWT) | PASS | baseline_p50_ms=0.0151; recovered_p50_ms=0.0223; recovery_ratio=1.48; burst_errors=0 | recovery_ratio<3 |
| 过载恢复(G代码生成) | PASS | baseline_p50_ms=0.575; recovered_p50_ms=0.307; recovery_ratio=0.53 | recovery_ratio<3 |

**合计：18/18 通过**
