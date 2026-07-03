# 性能基准测试报告

**生成时间**: 2026-06-26 16:28:06
**状态**: [PASS] 未检测到性能回退

## 回归检测结果

| 指标 | 当前值 | 上次值 | 变化率 | 状态 |
|------|--------|--------|--------|------|
| aggregate_query_ms_mean | 1.054 | 1.054 | +0.0% | [OK] PASS |
| aggregate_query_ms_p50 | 1.035 | 1.035 | +0.0% | [OK] PASS |
| aggregate_query_ms_p95 | 1.367 | 1.367 | +0.0% | [OK] PASS |
| asyncio_avg_ms | 16.810 | 16.810 | +0.0% | [OK] PASS |
| asyncio_p50_ms | 16.840 | 16.840 | +0.0% | [OK] PASS |
| asyncio_p95_ms | 18.070 | 18.070 | +0.0% | [OK] PASS |
| asyncio_rps | 4709.070 | 4709.070 | +0.0% | [OK] PASS |
| asyncio_tasks | 100.000 | 100.000 | +0.0% | [OK] PASS |
| asyncio_total_ms | 21.240 | 21.240 | +0.0% | [OK] PASS |
| avg_per_part_s | 0.070 | 0.070 | +0.0% | [OK] PASS |
| batch_100_inference_ms | 7.900 | 7.900 | +0.0% | [OK] PASS |
| batch_100_throughput_sps | 63278.300 | 63278.300 | +0.0% | [OK] PASS |
| batch_10_inference_ms | 16.380 | 16.380 | +0.0% | [OK] PASS |
| batch_10_throughput_sps | 12213.300 | 12213.300 | +0.0% | [OK] PASS |
| batch_50_inference_ms | 8.930 | 8.930 | +0.0% | [OK] PASS |
| batch_50_throughput_sps | 55977.900 | 55977.900 | +0.0% | [OK] PASS |
| cpu_stress_duration_s | 2.000 | 2.000 | +0.0% | [OK] PASS |
| cpu_stress_iterations | 138.000 | 138.000 | +0.0% | [OK] PASS |
| cpu_stress_ops_per_s | 68.920 | 68.920 | +0.0% | [OK] PASS |
| drawing_parse_s | 0.060 | 0.060 | +0.0% | [OK] PASS |
| drawing_parse_s_max | 0.022 | 0.022 | +0.0% | [OK] PASS |
| drawing_parse_s_mean | 0.018 | 0.018 | +0.0% | [OK] PASS |
| drawing_parse_s_min | 0.016 | 0.016 | +0.0% | [OK] PASS |
| drawing_parse_s_p50 | 0.016 | 0.016 | +0.0% | [OK] PASS |
| drawing_parse_s_p95 | 0.022 | 0.022 | +0.0% | [OK] PASS |
| drawing_parse_views | 3.000 | 3.000 | +0.0% | [OK] PASS |
| gpu_inference_ms_mean | 6.431 | 6.431 | +0.0% | [OK] PASS |
| gpu_inference_ms_p50 | 0.429 | 0.429 | +0.0% | [OK] PASS |
| gpu_inference_ms_p95 | 120.045 | 120.045 | +0.0% | [OK] PASS |
| gpu_memory_mb | 9.400 | 9.400 | +0.0% | [OK] PASS |
| indexed_query_ms_mean | 0.285 | 0.285 | +0.0% | [OK] PASS |
| indexed_query_ms_p50 | 0.276 | 0.276 | +0.0% | [OK] PASS |
| indexed_query_ms_p95 | 0.337 | 0.337 | +0.0% | [OK] PASS |
| insert_batch_ms | 70.840 | 70.840 | +0.0% | [OK] PASS |
| insert_per_row_ms | 0.071 | 0.071 | +0.0% | [OK] PASS |
| insert_throughput_rps | 14116.100 | 14116.100 | +0.0% | [OK] PASS |
| join_query_ms_mean | 0.157 | 0.157 | +0.0% | [OK] PASS |
| join_query_ms_p50 | 0.128 | 0.128 | +0.0% | [OK] PASS |
| join_query_ms_p95 | 0.459 | 0.459 | +0.0% | [OK] PASS |
| lnn_inference_ms_max | 1.763 | 1.763 | +0.0% | [OK] PASS |
| lnn_inference_ms_mean | 1.057 | 1.057 | +0.0% | [OK] PASS |
| lnn_inference_ms_min | 0.868 | 0.868 | +0.0% | [OK] PASS |
| lnn_inference_ms_p50 | 0.996 | 0.996 | +0.0% | [OK] PASS |
| lnn_inference_ms_p95 | 1.439 | 1.439 | +0.0% | [OK] PASS |
| lnn_inference_ms_p99 | 1.763 | 1.763 | +0.0% | [OK] PASS |
| lnn_inference_samples | 1.000 | 1.000 | +0.0% | [OK] PASS |
| memory_object_growth | 2.000 | 2.000 | +0.0% | [OK] PASS |
| memory_pressure_avg_ms | 8.670 | 8.670 | +0.0% | [OK] PASS |
| memory_pressure_iterations | 50.000 | 50.000 | +0.0% | [OK] PASS |
| memory_pressure_p50_ms | 8.700 | 8.700 | +0.0% | [OK] PASS |
| memory_pressure_p95_ms | 10.810 | 10.810 | +0.0% | [OK] PASS |
| model_load_s | 0.010 | 0.010 | +0.0% | [OK] PASS |
| nc_generation_total_s | 0.210 | 0.210 | +0.0% | [OK] PASS |
| parts_processed | 3.000 | 3.000 | +0.0% | [OK] PASS |
| post_processing_s | 0.005 | 0.005 | +0.0% | [OK] PASS |
| post_processor_ms_mean | 0.020 | 0.020 | +0.0% | [OK] PASS |
| post_processor_ms_p50 | 0.020 | 0.020 | +0.0% | [OK] PASS |
| post_processor_ms_p95 | 0.020 | 0.020 | +0.0% | [OK] PASS |
| process_planning_ms_mean | 1.310 | 1.310 | +0.0% | [OK] PASS |
| process_planning_ms_p50 | 1.180 | 1.180 | +0.0% | [OK] PASS |
| process_planning_ms_p95 | 1.920 | 1.920 | +0.0% | [OK] PASS |
| process_planning_s | 0.037 | 0.037 | +0.0% | [OK] PASS |
| reconstruction_s | 0.094 | 0.094 | +0.0% | [OK] PASS |
| simple_query_ms_mean | 0.128 | 0.128 | +0.0% | [OK] PASS |
| simple_query_ms_p50 | 0.117 | 0.117 | +0.0% | [OK] PASS |
| simple_query_ms_p95 | 0.213 | 0.213 | +0.0% | [OK] PASS |
| sustained_avg_ms | 0.130 | 0.130 | +0.0% | [OK] PASS |
| sustained_duration_s | 3.000 | 3.000 | +0.0% | [OK] PASS |
| sustained_errors | 0.000 | 0.000 | +0.0% | [NEW] NEW |
| sustained_p50_ms | 0.100 | 0.100 | +0.0% | [OK] PASS |
| sustained_p95_ms | 0.310 | 0.310 | +0.0% | [OK] PASS |
| sustained_requests | 113790.000 | 113790.000 | +0.0% | [OK] PASS |
| sustained_rps | 37926.130 | 37926.130 | +0.0% | [OK] PASS |
| sustained_success_rate | 100.000 | 100.000 | +0.0% | [OK] PASS |
| thread_pool_avg_ms | 26.570 | 26.570 | +0.0% | [OK] PASS |
| thread_pool_p50_ms | 26.410 | 26.410 | +0.0% | [OK] PASS |
| thread_pool_p95_ms | 34.560 | 34.560 | +0.0% | [OK] PASS |
| thread_pool_rps | 353.730 | 353.730 | +0.0% | [OK] PASS |
| thread_pool_tasks | 50.000 | 50.000 | +0.0% | [OK] PASS |
| thread_pool_total_ms | 141.350 | 141.350 | +0.0% | [OK] PASS |
| thread_pool_workers | 10.000 | 10.000 | +0.0% | [OK] PASS |
| toolpath_gen_ms_mean | 2.390 | 2.390 | +0.0% | [OK] PASS |
| toolpath_gen_ms_p50 | 2.330 | 2.330 | +0.0% | [OK] PASS |
| toolpath_gen_ms_p95 | 3.220 | 3.220 | +0.0% | [OK] PASS |
| toolpath_generation_s | 0.014 | 0.014 | +0.0% | [OK] PASS |