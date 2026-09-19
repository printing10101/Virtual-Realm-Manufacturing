# 西门子标准极限压力测试报告

- 生成时间：2026-09-18 05:40:20
- Python：3.14.4
- psutil：7.2.2
- 平台：Windows-11-10.0.26200-SP0

## 结果汇总

| 测试 | 状态 | 关键指标 | 阈值 |
|------|------|----------|------|
| 并发JWT创建+验签 | PASS | avg=0.05011; p50=0.0331; p95=0.1239; p99=0.2691; max=1.47; count=5000; qps=1.16e+04; total_ms=430.9 | p99<1 |
| 并发G代码生成 | PASS | avg=1.277; p50=0.7039; p95=1.778; p99=17.04; max=38.42; count=1000; generated=1000; avg_lines=64.25 | errors<1 |
| 并发工艺规划 | PASS | avg=0.243; p50=0.1933; p95=0.5236; p99=0.9526; max=0.9979; count=600; total=600 | errors<1 |
| 并发心跳调度(独立DB) | PASS | threads=10; tasks_per_thread=200; due_counts=[200,200,200,200,200...] | errors<1 |
| JWT验签吞吐量 | PASS | avg=0.04088; p50=0.0311; p95=0.0837; p99=0.1798; max=1.577; count=5000; qps=2.446e+04 | qps≥1000; p99<1 |
| G代码生成吞吐量 | PASS | avg=0.8177; p50=0.7019; p95=1.452; p99=2.377; max=2.819; count=200; qps=1223 | avg<10; p99<30 |
| 实时传感器处理吞吐量 | PASS | avg=0.01034; p50=0.0055; p95=0.0129; p99=0.0261; max=21.27; count=1e+04; qps=9.672e+04 | p99<1 |
| 审计日志写入吞吐量 | PASS | avg=0.152; p50=0.0636; p95=0.3281; p99=2.062; max=6.437; count=3000; qps=6577; integrity=1 | avg<5; p99<10 |
| 心跳调度add_task吞吐量 | PASS | avg=0.6152; p50=0.4791; p95=1.011; p99=3.874; max=15.33; count=2000; qps=1626 | avg<10 |
| G代码生成浸泡(2000次) | PASS | baseline_rss_mb=1354; final_growth_pct=0; tail_growth_pct=0; max_growth_pct=0 | growth<15 |
| 审计日志浸泡(3000条) | PASS | baseline_rss_mb=1354; tail_growth_pct=-0; max_growth_pct=-0; integrity=1 | growth<15 |
| 浸泡延迟漂移(JWT) | PASS | first_p95_ms=0.0921; tail_p95_ms=0.1147; drift_ratio=1.25 | drift_ratio<3 |
| 满负荷资源阈值 | FAIL | cpu_avg=94.9; cpu_max=99.1; sys_mem_avg=91.8; sys_mem_delta=0; baseline_sys_mem=92; app_peak_rss_mb=1355; app_baseline_rss_mb=1354; net_avg_mbps=0.16; net_max_mbps=0.85 | cpu<90; net<50; app_rss_mb<1024; sys_mem_delta_pct<5 |
| G代码生成错误率 | PASS | error_rate_pct=0; errors=0; empty=0 | error_rate<1 |
| 心跳调度错误率 | PASS | error_rate_pct=0; errors=0 | error_rate<1 |
| 并发预算检查错误率 | PASS | error_rate_pct=0; errors=0 | error_rate<1 |
| 过载恢复(JWT) | PASS | baseline_p50_ms=0.0274; recovered_p50_ms=0.0277; recovery_ratio=1.01; burst_errors=0 | recovery_ratio<3 |
| 过载恢复(G代码生成) | PASS | baseline_p50_ms=0.594; recovered_p50_ms=0.576; recovery_ratio=0.97 | recovery_ratio<3 |

**合计：17/18 通过**

## 未通过项明细

### 满负荷资源阈值
- 状态：FAIL
- 指标：{
  "cpu_avg": 94.9,
  "cpu_max": 99.1,
  "sys_mem_avg": 91.8,
  "sys_mem_delta": 0.0,
  "baseline_sys_mem": 92.0,
  "app_peak_rss_mb": 1354.8,
  "app_baseline_rss_mb": 1354.2,
  "net_avg_mbps": 0.16,
  "net_max_mbps": 0.85
}
- 阈值：{
  "cpu": 90.0,
  "net": 50.0,
  "app_rss_mb": 1024.0,
  "sys_mem_delta_pct": 5.0
}
- 备注：6相位混合负载；硬门禁为应用可归因指标，系统绝对占用仅参考

