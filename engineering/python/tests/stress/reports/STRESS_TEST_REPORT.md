# 西门子标准极限压力测试报告

- 生成时间：2026-09-07 06:16:05
- Python：3.14.4
- psutil：7.2.2
- 平台：Windows-11-10.0.26200-SP0

## 结果汇总

| 测试 | 状态 | 关键指标 | 阈值 |
|------|------|----------|------|
| 并发JWT创建+验签 | PASS | avg=0.02115; p50=0.0158; p95=0.0427; p99=0.0824; max=0.2445; count=5000; qps=3.533e+04; total_ms=141.5 | p99<1 |
| 并发G代码生成 | PASS | avg=0.35; p50=0.2846; p95=0.6591; p99=1.118; max=1.908; count=1000; generated=1000; avg_lines=64.25 | errors<1 |
| 并发工艺规划 | PASS | avg=0.1004; p50=0.0895; p95=0.1698; p99=0.22; max=0.3424; count=600; total=600 | errors<1 |
| 并发心跳调度(独立DB) | PASS | threads=10; tasks_per_thread=200; due_counts=[200,200,200,200,200...] | errors<1 |
| JWT验签吞吐量 | PASS | avg=0.01616; p50=0.0147; p95=0.0259; p99=0.0414; max=0.1199; count=5000; qps=6.19e+04 | qps≥1000; p99<1 |
| G代码生成吞吐量 | PASS | avg=0.3321; p50=0.2853; p95=0.5507; p99=0.7275; max=0.7565; count=200; qps=3011 | avg<10; p99<30 |
| 实时传感器处理吞吐量 | PASS | avg=0.004926; p50=0.0035; p95=0.0109; p99=0.0195; max=0.1989; count=1e+04; qps=2.03e+05 | p99<1 |
| 审计日志写入吞吐量 | PASS | avg=0.06005; p50=0.0226; p95=0.0729; p99=1.152; max=1.87; count=3000; qps=1.665e+04; integrity=1 | avg<5; p99<10 |
| 心跳调度add_task吞吐量 | PASS | avg=0.3126; p50=0.2286; p95=0.5483; p99=2.191; max=7.788; count=2000; qps=3199 | avg<10 |
| G代码生成浸泡(2000次) | PASS | baseline_rss_mb=1376; final_growth_pct=0; tail_growth_pct=0; max_growth_pct=0 | growth<15 |
| 审计日志浸泡(3000条) | PASS | baseline_rss_mb=1376; tail_growth_pct=0; max_growth_pct=0; integrity=1 | growth<15 |
| 浸泡延迟漂移(JWT) | PASS | first_p95_ms=0.0308; tail_p95_ms=0.0485; drift_ratio=1.58 | drift_ratio<3 |
| 满负荷资源阈值 | FAIL | cpu_avg=6.7; cpu_max=10.2; sys_mem_avg=63.5; sys_mem_delta=0; baseline_sys_mem=63.5; app_peak_rss_mb=1381; app_baseline_rss_mb=1376; net_avg_mbps=0.01; net_max_mbps=0.02 | cpu<90; net<50; app_rss_mb<1024; sys_mem_delta_pct<5 |
| G代码生成错误率 | PASS | error_rate_pct=0; errors=0; empty=0 | error_rate<1 |
| 心跳调度错误率 | PASS | error_rate_pct=0; errors=0 | error_rate<1 |
| 并发预算检查错误率 | PASS | error_rate_pct=0; errors=0 | error_rate<1 |
| 过载恢复(JWT) | PASS | baseline_p50_ms=0.0161; recovered_p50_ms=0.0151; recovery_ratio=0.94; burst_errors=0 | recovery_ratio<3 |
| 过载恢复(G代码生成) | PASS | baseline_p50_ms=0.277; recovered_p50_ms=0.271; recovery_ratio=0.98 | recovery_ratio<3 |

**合计：17/18 通过**

## 未通过项明细

### 满负荷资源阈值
- 状态：FAIL
- 指标：{
  "cpu_avg": 6.7,
  "cpu_max": 10.2,
  "sys_mem_avg": 63.5,
  "sys_mem_delta": 0.0,
  "baseline_sys_mem": 63.5,
  "app_peak_rss_mb": 1381.4,
  "app_baseline_rss_mb": 1376.1,
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

