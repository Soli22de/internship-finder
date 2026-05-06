# 项目目录说明

## 核心代码
- `official_multi_crawler.py`：官方站抓取主入口（快手/腾讯/小红书/美团）
- `merge_file.py`：合并清洗、评分、目标池与看板输出
- `parsers/`：公司适配器
- `rules/`：届别规则、城市归一规则
- `utils/link_checker.py`：轻量异步链接健康检查
- `run_kuaishou_daily.ps1`：每日自动化运行脚本
- `run_task6_pipeline.ps1`：Task6全链路调度执行脚本
- `register_task6_schedule.ps1`：Task6计划任务注册脚本
- `organize_workspace.ps1`：产物目录整理脚本

## 历史归档
- `archive/history/shixiseng/`：实习僧历史抓取脚本与数据
- `archive/history/legacy_runs/`：历史跑批快照与旧实验文件
- `archive/history/debug/`：历史调试与排障材料

## 常用输出
- `official_jobs_raw.csv`：官方抓取原始汇总
- `outputs/reports/`：主库、目标池、Top20等分析结果
- `outputs/dashboard/`：公司看板与多公司总览
- `outputs/health/`：链接健康检查结果与历史状态
