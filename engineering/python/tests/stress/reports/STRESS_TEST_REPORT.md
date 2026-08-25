# 西门子标准极限压力测试报告

- 生成时间：2026-08-23 21:02:34
- Python：3.14.3
- psutil：7.1.3
- 平台：Windows-11-10.0.26200-SP0

## 结果汇总

| 测试 | 状态 | 关键指标 | 阈值 |
|------|------|----------|------|
| 并发JWT创建+验签 | PASS | avg=0.01869; p50=0.0157; p95=0.0306; p99=0.0467; max=0.1584; count=5000; qps=4.41e+04; total_ms=113.4 | p99<1 |
| 并发G代码生成 | PASS | avg=0.4185; p50=0.3531; p95=0.6717; p99=0.8533; max=15.37; count=1000; generated=1000; avg_lines=64.25 | errors<1 |
| 并发工艺规划 | PASS | avg=0.1242; p50=0.0982; p95=0.1989; p99=0.2455; max=0.3804; count=600; total=600 | errors<1 |
| 并发心跳调度(独立DB) | PASS | threads=10; tasks_per_thread=200; due_counts=[200,200,200,200,200...] | errors<1 |
| JWT验签吞吐量 | PASS | avg=0.02386; p50=0.0242; p95=0.034; p99=0.0495; max=0.216; count=5000; qps=4.192e+04 | qps≥1000; p99<1 |
| G代码生成吞吐量 | PASS | avg=0.4926; p50=0.4725; p95=0.8434; p99=1.231; max=1.38; count=200; qps=2030 | avg<10; p99<30 |
| 实时传感器处理吞吐量 | PASS | avg=0.007922; p50=0.0048; p95=0.0074; p99=0.0187; max=27.93; count=1e+04; qps=1.262e+05 | p99<1 |
| 审计日志写入吞吐量 | PASS | avg=0.06808; p50=0.0304; p95=0.0979; p99=1.274; max=1.873; count=3000; qps=1.469e+04; integrity=1 | avg<5; p99<10 |
| 心跳调度add_task吞吐量 | PASS | avg=0.2208; p50=0.1352; p95=0.2703; p99=3.109; max=15.26; count=2000; qps=4529 | avg<10 |
| G代码生成浸泡(2000次) | PASS | baseline_rss_mb=121.3; final_growth_pct=0; tail_growth_pct=0; max_growth_pct=0 | growth<15 |
| 审计日志浸泡(3000条) | PASS | baseline_rss_mb=121.4; tail_growth_pct=0; max_growth_pct=0; integrity=1 | growth<15 |
| 浸泡延迟漂移(JWT) | PASS | first_p95_ms=0.0319; tail_p95_ms=0.0359; drift_ratio=1.12 | drift_ratio<3 |
| 满负荷资源阈值 | PASS | cpu_avg=32.5; cpu_max=39.2; sys_mem_avg=76.9; sys_mem_delta=0; baseline_sys_mem=77; app_peak_rss_mb=127.8; app_baseline_rss_mb=121.8; net_avg_mbps=0.81; net_max_mbps=1.63 | cpu<80; net<50; app_rss_mb<1024; sys_mem_delta_pct<5 |
| G代码生成错误率 | PASS | error_rate_pct=0; errors=0; empty=0 | error_rate<1 |
| 心跳调度错误率 | PASS | error_rate_pct=0; errors=0 | error_rate<1 |
| 并发预算检查错误率 | PASS | error_rate_pct=0; errors=0 | error_rate<1 |
| 过载恢复(JWT) | PASS | baseline_p50_ms=0.0149; recovered_p50_ms=0.0238; recovery_ratio=1.6; burst_errors=0 | recovery_ratio<3 |
| 过载恢复(G代码生成) | PASS | baseline_p50_ms=0.482; recovered_p50_ms=0.541; recovery_ratio=1.12 | recovery_ratio<3 |

**合计：18/18 通过**
