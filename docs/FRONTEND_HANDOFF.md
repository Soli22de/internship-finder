# Mini-Program Frontend Handoff

## 项目状态

FastAPI 后端 + 11个爬虫 + 385条实习数据已入库。前端骨架已经建好，需要 Opus 优化 UX/UI。

## API Endpoints

Base URL: `http://127.0.0.1:8000`

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/health` | 系统状态 |
| GET | `/api/stats` | 数据统计（总数/各源） |
| GET | `/api/jobs?city=上海&source=&keyword=&limit=20&offset=0` | 岗位列表 |
| GET | `/api/jobs/{id}` | 岗位详情 |
| POST | `/api/match` | 简历匹配 `{resume_text, city, top_n}` |
| POST | `/api/crawl` | 触发爬取 `{sources: ["tencent"]}` |

## 数据字段

```json
{
  "id": 1,
  "title": "数据分析实习生",
  "company": "字节跳动",
  "city": "上海",
  "salary": "200-250元/天",
  "jd_raw": "岗位职责：...",
  "url": "https://...",
  "source": "bytedance",
  "recruit_type": "实习",
  "publish_time": "2026-05-01",
  "deadline": "",
  "raw_tags": "",
  "match_score": 85.5
}
```

## 现有页面（骨架）

`miniprogram/pages/` 下已有5页，都是最简框架，需要 Opus 优化：

| 页面 | 现有功能 | 需要优化 |
|------|----------|----------|
| `index` | 列表+搜索+筛选 | 卡片样式、加载动效、下拉刷新手感 |
| `detail` | 信息展示+复制链接 | 骨架屏、JD排版、投递交互 |
| `match` | 简历输入+匹配结果 | 拖拽上传、匹配动效、分数可视化 |
| `track` | 已投递列表 | 日历视图、状态管理、通知 |
| `profile` | 统计+设置 | 设置页设计、数据源管理 |

## 设计要求

- 色彩：主色 `#1a73e8`，辅色 `#e84830`（薪资/匹配分数）
- 风格：清爽、简洁，参考 知页/实习僧 的卡片设计
- 字体：系统默认（微信小程序限制）
- Tab：首页 / 匹配 / 投递 / 我的

## Tab 图标

需要4个 tab icon（PNG 28x28px），当前 `images/` 目录是空的，请自行设计或提供占位。

## 工作流程

1. 设计师给 Figma / 截图
2. 实现 WXML + WXSS
3. 微信开发者工具预览
4. 联调后端 API

## 后端联系人

API 和数据结构由我负责，前端只管调接口。
任何新增字段或接口需求可以提，我加。
