# 西门子标准极限压力测试报告

- 生成时间：2026-09-07 02:48:03
- Python：3.14.4
- psutil：7.2.2
- 平台：Windows-11-10.0.26200-SP0

## 结果汇总

| 测试 | 状态 | 关键指标 | 阈值 |
|------|------|----------|------|
| 并发JWT创建+验签 | PASS | avg=0.0177; p50=0.016; p95=0.0267; p99=0.0418; max=0.5682; count=5000; qps=3.97e+04; total_ms=126 | p99<1 |
| 并发G代码生成 | PASS | avg=0.314; p50=0.2827; p95=0.4557; p99=0.733; max=0.9536; count=1000; generated=1000; avg_lines=64.25 | errors<1 |
| 并发工艺规划 | PASS | avg=0.089; p50=0.0836; p95=0.1083; p99=0.2453; max=0.3769; count=600; total=600 | errors<1 |
| 并发心跳调度(独立DB) | PASS | threads=10; tasks_per_thread=200; due_counts=[200,200,200,200,200...] | errors<1 |
| JWT验签吞吐量 | PASS | avg=0.01446; p50=0.0138; p95=0.0169; p99=0.021; max=0.1355; count=5000; qps=6.916e+04 | qps≥1000; p99<1 |
| G代码生成吞吐量 | PASS | avg=0.3069; p50=0.2784; p95=0.441; p99=0.5975; max=0.6167; count=200; qps=3259 | avg<10; p99<30 |
| 实时传感器处理吞吐量 | PASS | avg=0.002937; p50=0.0026; p95=0.004; p99=0.0064; max=0.0603; count=1e+04; qps=3.405e+05 | p99<1 |
| 审计日志写入吞吐量 | PASS | avg=0.05477; p50=0.0198; p95=0.0662; p99=1.055; max=1.555; count=3000; qps=1.826e+04; integrity=1 | avg<5; p99<10 |
| 心跳调度add_task吞吐量 | PASS | avg=0.2507; p50=0.1871; p95=0.3096; p99=2.214; max=7.941; count=2000; qps=3989 | avg<10 |
| G代码生成浸泡(2000次) | PASS | baseline_rss_mb=1376; final_growth_pct=0; tail_growth_pct=0; max_growth_pct=0 | growth<15 |
| 审计日志浸泡(3000条) | PASS | baseline_rss_mb=1376; tail_growth_pct=0; max_growth_pct=0; integrity=1 | growth<15 |
| 浸泡延迟漂移(JWT) | PASS | first_p95_ms=0.017; tail_p95_ms=0.018; drift_ratio=1.06 | drift_ratio<3 |
| 满负荷资源阈值 | FAIL | cpu_avg=20; cpu_max=27.7; sys_mem_avg=70.5; sys_mem_delta=-0.2; baseline_sys_mem=70.8; app_peak_rss_mb=1383; app_baseline_rss_mb=1377; net_avg_mbps=1.14; net_max_mbps=2.66 | cpu<90; net<50; app_rss_mb<1024; sys_mem_delta_pct<5 |
| G代码生成错误率 | PASS | error_rate_pct=0; errors=0; empty=0 | error_rate<1 |
| 心跳调度错误率 | PASS | error_rate_pct=0; errors=0 | error_rate<1 |
| 并发预算检查错误率 | PASS | error_rate_pct=0; errors=0 | error_rate<1 |
| 过载恢复(JWT) | PASS | baseline_p50_ms=0.0159; recovered_p50_ms=0.016; recovery_ratio=1.01; burst_errors=0 | recovery_ratio<3 |
| 过载恢复(G代码生成) | PASS | baseline_p50_ms=0.293; recovered_p50_ms=0.3; recovery_ratio=1.02 | recovery_ratio<3 |

**合计：17/18 通过**

## 未通过项明细

### 满负荷资源阈值
- 状态：FAIL
- 指标：{
  "cpu_avg": 20.0,
  "cpu_max": 27.7,
  "sys_mem_avg": 70.5,
  "sys_mem_delta": -0.2,
  "baseline_sys_mem": 70.8,
  "app_peak_rss_mb": 1383.1,
  "app_baseline_rss_mb": 1377.2,
  "net_avg_mbps": 1.14,
  "net_max_mbps": 2.66
}
- 阈值：{
  "cpu": 90.0,
  "net": 50.0,
  "app_rss_mb": 1024.0,
  "sys_mem_delta_pct": 5.0
}
- 备注：6相位混合负载；硬门禁为应用可归因指标，系统绝对占用仅参考

