## 目标
创建“internship_data_analysis_homework”文件夹，将与作业相关的数据、代码、Notebook 与分析报告完整整理到该目录；统一命名与路径，添加说明与依赖清单；执行一次可运行性验证与结构检查，最终生成可在另一台设备直接运行的作业包。

## 目录结构
- 根目录：`internship_data_analysis_homework/`
  - `data/`
    - `raw/`：原始数据（CSV/Excel）
    - `clean/`：清洗后数据（CSV）
  - `notebooks/`
    - `internship_analysis.ipynb`：主 Notebook（含爬取→清洗→分析→可视化→报告）
  - `reports/`
    - `internship_analysis.html`：导出的可视化报告（HTML）
    - 可选：`internship_analysis.pdf`
  - `src/`（可选）
    - `utils.py` 或 `scraper.py`：若需拆分函数
  - `assets/figures/`：需要时保存图表静态文件
  - `docs/`
    - `README.md`：运行说明、依赖、文件说明、作业要求对照表
  - 根级辅助文件：`requirements.txt`、`environment.yml`（可选）、`run.ps1`/`run.sh`（一键执行）

## 文件整理与命名
- 复制并统一命名：
  - 原始数据：`data/raw/internships_raw.csv`
  - 清洗数据：`data/clean/internships_clean.csv`
  - Notebook：`notebooks/internship_analysis.ipynb`
  - 报告：`reports/internship_analysis.html`
- 确保 Notebook 使用相对路径：`./data/raw/...`、`./data/clean/...`。

## 依赖与可运行性
- 依赖清单：`requests`、`beautifulsoup4`、`pandas`、`numpy`、`matplotlib`、`seaborn`、`tqdm`、`python-dateutil`、`jupyter`、`nbconvert`、`requests-html`（动态渲染回退）。
- 在 `requirements.txt` 中列出；`README.md` 提供安装与运行步骤。
- 一键脚本（可选）：
  - Windows：`run.ps1` 执行安装依赖→运行 Notebook（nbconvert 执行）→导出报告。
  - Mac/Linux：`run.sh` 同等逻辑。

## 检查与验证
1. 内容检查：
   - 存在原始与清洗数据文件、Notebook、报告、依赖清单与 README；辅助脚本/资源齐备。
2. 结构合理性：
   - 命名统一、路径引用正确、相对路径在 Notebook 中可用。
3. 功能完整性：
   - 使用 `nbconvert --execute` 在本机跑通并重新生成清洗数据与报告；图表与统计正常输出。
4. 最终验证：
   - 压缩为 `internship_data_analysis_homework.zip`，在另一台设备按照 README 安装依赖后运行；确认无缺文件、无路径错误、无无关文件（排除缓存/临时文件）。

## 作业要求对照
- 数据获取：Notebook 包含爬取（含 Cookie 预热与动态回退）与节流异常处理。
- 数据清洗：缺失值与重复处理、标准化映射、薪资单位统一。
- 数据分析：分维度统计与上海本科专项。
- 可视化：直方图、饼图、条形图、箱线图；标题/标签/图例完整。
- 报告生成：Notebook 内含 Markdown；导出 HTML（可选 PDF）。

## 执行步骤（确认后）
1. 新建目标目录并按结构复制/移动现有文件。
2. 校验并（必要时）调整 Notebook 的相对路径与配置。
3. 生成 `requirements.txt` 与 `README.md`；可选生成一键运行脚本。
4. 本机使用 `nbconvert` 执行一次，输出报告与 CSV 到目标目录。
5. 压缩为 zip，进行跨设备验证。
6. 提交最终作业包。