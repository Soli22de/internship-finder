## 项目目标
为“实习僧”岗位数据建立一个可复现的 Jupyter Notebook 项目，覆盖数据爬取→清洗→分析→可视化→报告，重点针对“上海地区本科生”的就业情况做专项分析与结论。

## 环境与依赖
- 运行环境：`Python 3.10+`、`Jupyter Notebook`
- 依赖库：`requests`、`beautifulsoup4`、`pandas`、`numpy`、`matplotlib`、`seaborn`、`tqdm`、`python-dateutil`
- 中文显示：在绘图前设置 `plt.rcParams['font.sans-serif']=['SimHei']` 与 `plt.rcParams['axes.unicode_minus']=False`

## 数据字段与结构
- 原始字段：`title`(职位名称)、`company`(公司名称)、`city`、`district`(区县)、`salary_text`(原始薪资文本)、`education`、`experience`、`publish_date`、`job_url`、`source`
- 解析字段：`salary_min`、`salary_max`、`salary_unit`(`元`/`K`)、`salary_period`(`天`/`月`)、`salary_avg`
- 清洗后补充：`city_std`、`district_std`、`education_std`、`experience_std`、`salary_month_cny`(统一月薪，单位人民币)
- 文件结构（交付物）：`data/raw/internships_raw.csv`、`data/clean/internships_clean.csv`、Notebook 内嵌图表；图像可选保存到 `assets/figures/`。

## 爬取策略（requests + BeautifulSoup）
- 目标站点：实习僧公开列表页与岗位详情页（仅学习用途）
- 入口参数：`city='上海'`，支持翻页 `page=1..N`
- 请求配置：自定义 `User-Agent`、`Referer`、`Accept-Language`；超时、重试（指数退避）；失败日志。
- 反爬与节流：随机间隔 `1.5–3.8s`；分页间隔更长；必要时引入简单代理（不默认启用）。
- 解析逻辑：
  - 列表页：提取每条岗位卡片的链接、标题、公司、地点、薪资文本、教育/经验简要。
  - 详情页（可选）：补充缺失字段与发布时间。
- 异常处理：针对网络异常、结构变化、字段缺失进行 `try/except` 捕获；不可解析的样本保留并标记，以便清洗阶段处理。

## 清洗规则（pandas）
- 缺失值：
  - 关键字段缺失（`title`/`company`）剔除；
  - `education`/`experience` 缺失填充为 `未注明`；
  - `district` 缺失但 `city=上海` 时尝试从文本中提取，否则标记 `未知`。
- 异常值：
  - 薪资文本解析失败标记；
  - 使用 IQR 检测极端薪资（如 > 10W/月 或 < 500/月）并审慎裁剪或标注。
- 重复：按 `title+company+job_url` 去重。
- 标准化：
  - 薪资统一到 “月薪（人民币）”：将 `元/天`、`K/月` 等转换；若给区间，取区间中位数作为 `salary_month_cny`；
  - 地点：统一城市/区县中文名；为上海建立区县映射（如 `浦东新区`、`徐汇区`、`静安区` 等）；
  - 学历：映射为 `{高中/中专, 大专, 本科, 硕士, 博士, 不限, 未注明}`；
  - 经验：映射为 `{经验不限, 在校生/应届, 1年+, 2年+, 未注明}`；
- 输出：保存清洗后数据到 `data/clean/internships_clean.csv`。

## 分析指标（pandas/numpy）
- 全局：岗位数量、平均/中位数月薪、IQR、各学历占比、经验要求分布。
- 地区维度：上海各区县的岗位数量、平均/中位数薪资排名。
- 学历维度：不同学历的岗位数量与薪资统计（均值/中位数/分位数）。
- 经验维度：不同经验要求的岗位数量与薪资统计。
- 公司维度：Top 10 发布岗位公司及对应薪资区间概览。

## 上海本科专项分析
- 过滤条件：`city_std == '上海' and education_std == '本科'`
- 统计：岗位数量、平均/中位数薪资、分位数（P25/P75）、区县分布 Top、行业/公司 Top（若有行业字段则统计，否则以公司为主）。
- 结论要点：薪资水平区间、机会集中区域、对求职建议（如区县差异、公司偏好、经验要求对薪资的影响等）。

## 可视化图表（matplotlib/seaborn）
- 薪资分布直方图：全体样本与“上海本科”子集对比；添加 KDE。
- 地区分布饼图：上海各区岗位占比；
- 学历要求条形图：各学历岗位数量；
- 箱线图：不同学历或不同区县的薪资分布；
- Top 公司条形图：按岗位数量或平均薪资排序；
- 美化：统一主题、中文标题与标签、图例、数据标签；必要时旋转刻度。

## Notebook 结构与内容组织
1. 项目说明（Markdown）：目标、方法、伦理说明（仅学习用途，遵循站点规则）。
2. 环境准备（代码）：导入与 `pip` 安装缺失依赖（可选）。
3. 参数配置（代码）：城市、最大页数、节流与重试、输出路径。
4. 爬虫实现（代码）：函数化实现列表页解析与详情页补充，带异常处理与日志；原始数据保存。
5. 数据清洗（代码+Markdown）：按上述规则处理并输出清洗后数据。
6. 数据概览（代码）：`head()`、`info()`、`describe()`；样本量与字段解释。
7. 统计分析（代码+图）：全局与分维度指标。
8. 可视化（代码+图）：各类图表，均含标题/标签/图例。
9. 上海本科专项（代码+图+Markdown）：深入分析与结论。
10. 总结与建议（Markdown）：基于分析结果形成结论与建议。

## 复现与合规
- 运行步骤：自上而下执行 Notebook；根据网络情况调整 `max_pages` 与 `sleep` 区间。
- 仅采集公开信息，不对站点造成压力；遵循 `robots.txt` 与服务条款；数据仅用于课程学习与研究。

## 交付物
- `internship_analysis.ipynb` 完整 Notebook（含注释与 Markdown 报告）。
- `data/raw/internships_raw.csv` 原始数据；`data/clean/internships_clean.csv` 清洗后数据。
- 所有图表嵌入 Notebook（可选另存为图片）。

## 下一步
- 获得确认后：
  - 在仓库中新增 Notebook，并实现爬虫、清洗、分析与可视化全部代码；
  - 试跑少量页（如 3–5 页）验证解析规则，再扩展；
  - 输出交付物并完善结论，特别是“上海本科生”专项部分。