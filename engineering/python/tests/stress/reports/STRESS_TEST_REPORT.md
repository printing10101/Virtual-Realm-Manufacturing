# 西门子标准极限压力测试报告

- 生成时间：2026-09-08 04:40:25
- Python：3.14.4
- psutil：7.2.2
- 平台：Windows-11-10.0.26200-SP0

## 结果汇总

| 测试 | 状态 | 关键指标 | 阈值 |
|------|------|----------|------|
| 并发JWT创建+验签 | PASS | avg=0.01542; p50=0.0142; p95=0.021; p99=0.0373; max=0.4342; count=5000; qps=4.746e+04; total_ms=105.4 | p99<1 |
| 并发G代码生成 | PASS | avg=0.2845; p50=0.2562; p95=0.3972; p99=0.7103; max=1.572; count=1000; generated=1000; avg_lines=64.25 | errors<1 |
| 并发工艺规划 | PASS | avg=0.09659; p50=0.0896; p95=0.1424; p99=0.2071; max=0.4091; count=600; total=600 | errors<1 |
| 并发心跳调度(独立DB) | PASS | threads=10; tasks_per_thread=200; due_counts=[200,200,200,200,200...] | errors<1 |
| JWT验签吞吐量 | PASS | avg=0.01491; p50=0.0138; p95=0.0157; p99=0.0396; max=0.2238; count=5000; qps=6.705e+04 | qps≥1000; p99<1 |
| G代码生成吞吐量 | PASS | avg=0.3209; p50=0.269; p95=0.6493; p99=0.9541; max=1.158; count=200; qps=3117 | avg<10; p99<30 |
| 实时传感器处理吞吐量 | PASS | avg=0.002862; p50=0.0026; p95=0.0037; p99=0.0058; max=0.0559; count=1e+04; qps=3.494e+05 | p99<1 |
| 审计日志写入吞吐量 | PASS | avg=0.04916; p50=0.0192; p95=0.0567; p99=0.8884; max=1.465; count=3000; qps=2.034e+04; integrity=1 | avg<5; p99<10 |
| 心跳调度add_task吞吐量 | PASS | avg=0.2332; p50=0.1663; p95=0.2852; p99=2.033; max=13.95; count=2000; qps=4287 | avg<10 |
| G代码生成浸泡(2000次) | PASS | baseline_rss_mb=2044; final_growth_pct=0; tail_growth_pct=0; max_growth_pct=0 | growth<15 |
| 审计日志浸泡(3000条) | PASS | baseline_rss_mb=2044; tail_growth_pct=0; max_growth_pct=0; integrity=1 | growth<15 |
| 浸泡延迟漂移(JWT) | PASS | first_p95_ms=0.0175; tail_p95_ms=0.0156; drift_ratio=0.89 | drift_ratio<3 |
| 满负荷资源阈值 | FAIL | cpu_avg=6.7; cpu_max=16.7; sys_mem_avg=88.2; sys_mem_delta=0; baseline_sys_mem=88.3; app_peak_rss_mb=2046; app_baseline_rss_mb=2044; net_avg_mbps=0.01; net_max_mbps=0.02 | cpu<90; net<50; app_rss_mb<1024; sys_mem_delta_pct<5 |
| G代码生成错误率 | PASS | error_rate_pct=0; errors=0; empty=0 | error_rate<1 |
| 心跳调度错误率 | PASS | error_rate_pct=0; errors=0 | error_rate<1 |
| 并发预算检查错误率 | PASS | error_rate_pct=0; errors=0 | error_rate<1 |
| 过载恢复(JWT) | PASS | baseline_p50_ms=0.0146; recovered_p50_ms=0.0137; recovery_ratio=0.94; burst_errors=0 | recovery_ratio<3 |
| 过载恢复(G代码生成) | PASS | baseline_p50_ms=0.26; recovered_p50_ms=0.259; recovery_ratio=0.99 | recovery_ratio<3 |

**合计：17/18 通过**

## 未通过项明细

### 满负荷资源阈值
- 状态：FAIL
- 指标：{
  "cpu_avg": 6.7,
  "cpu_max": 16.7,
  "sys_mem_avg": 88.2,
  "sys_mem_delta": 0.0,
  "baseline_sys_mem": 88.3,
  "app_peak_rss_mb": 2046.1,
  "app_baseline_rss_mb": 2044.4,
  "net_avg_mbps": 0.01,
  "net_max_mbps": 0.02
}
- 阈值：{
  "cpu": 90.0,
  "net": 50.0,
  "app_rss_mb": 1024.0,
  "sys_mem_delta_pct": 5.0
}
- 备注：6相位混合负载；硬门禁为应用可归因指标，系统绝对占用仅参考

