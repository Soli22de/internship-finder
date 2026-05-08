# Opus: 微信小程序前端 — 设计 + 实现

## 你的角色

你是这个项目的首席 UI/UX 设计师 + 前端实现者。后端和数据由另一个 AI 负责，你只关心 `miniprogram/` 目录。

## 项目概述

实习聚合平台。后端爬取了12个数据源（大厂官网+实习僧+BOSS+猎聘），共385+条实习岗位。
数据通过 FastAPI 提供，小程序直接调接口。

## 你的任务

优化 `miniprogram/` 下已有的5个页面骨架：

### 1. 首页（岗位列表）

现有：列表+搜索框+筛选条
需要：专业感十足的卡片设计。每个岗位卡片应有：
- 岗位名称（粗体，16px）
- 公司名 + 城市 + 数据源标签（一行）
- 薪资（红色突出）
- JD预览（两行省略）
- 整体要有层次感，信息密度适中

搜索框：始终固定在顶部，支持输入搜索和筛选标签。

### 2. 详情页

现有：头部信息 + JD正文 + 按钮
需要：
- 骨架屏加载态（Skeleton）
- 精美头部卡片（白底圆角，阴影浅）
- 薪资用特殊徽标样式
- JD正文要有段落间距，可读性强
- 底部固定操作栏：「复制链接去投递」「标记已投递」
- 标记后按钮变灰+勾选图标

### 3. 匹配页

现有：文本框 + 匹配按钮 + 结果列表
需要：
- 简历输入可以用文本框（MVP），但UI要好看：有示例提示文字，一个「填入示例简历」快捷按钮
- 匹配结果卡片：左侧大号匹配分数（圆形，渐变色），右侧岗位信息
- 匹配理由用浅灰色小字显示在卡片底部
- 空态设计

### 4. 投递追踪

现有：简单列表
需要：
- 「已投递 N 个岗位」的统计Header
- 卡片式列表
- 清除按钮
- 空态提示

### 5. 我的

现有：统计数字 + 数据源列表 + 设置
需要：
- 顶部用户信息占位（头像+昵称）
- 统计卡片（三个指标：岗位总数/数据源数/覆盖城市）
- 数据源列表显示每个源的名字和数量
- 「手动更新数据」按钮
- 目标城市选择器
- 美观的底部版本信息

### Tab Bar 图标

`miniprogram/images/` 下需要4个 tab icon（不需要真的PNG，用emoji或纯文字占位即可，标注清楚让开发者替换）

## 设计规范

```
主色: #1a73e8 (蓝色)
辅色: #e84830 (红色/薪资)
背景: #f5f5f5
卡片: #ffffff 圆角12px 浅阴影
字体: 系统默认
圆角: 按钮8px 卡片12px 标签16px
```

## 现有文件结构

```
miniprogram/
├── app.js              # 入口 (globalData: baseUrl)
├── app.json            # tabBar配置
├── app.wxss            # 全局样式（已有基础样式，按需覆盖）
├── project.config.json
├── sitemap.json
├── utils/
│   └── api.js          # 封装好的API调用(getJobs, getJob, matchResume等)
├── pages/
│   ├── index/          # home: index.js + index.wxml
│   ├── detail/         # detail: detail.js + detail.wxml
│   ├── match/          # match: match.js + match.wxml
│   ├── track/          # track: track.js + track.wxml
│   └── profile/        # profile: profile.js + profile.wxml
└── images/             # 空，需要你补
```

## API 接口文档

Base URL: 开发时 `http://127.0.0.1:8000`，上线后替换

```
GET  /api/health            → {status: "ok", total_active_jobs: 385, sources: {...}}
GET  /api/jobs?city=上海&limit=20&offset=0  → {total: 385, jobs: [...]}
GET  /api/jobs/{id}         → {id: 1, title: "...", company: "...", ...}
GET  /api/stats             → {total_active: 385, by_city: [...], by_source: [...]}
POST /api/match             → {top_matches: [{...id, title, match_score, match_reason...}]}
POST /api/match/llm         → {top_matches: [{...id, title, match_score, match_reason, hit_skills, gap_skills}]}
```

已知问题: 部分字段 (city, salary) 因为字体加密可能包含不可见字符，不影响显示。

## 不需要你做的

- 后端逻辑（API路由、数据库、爬虫）
- 用户登录/注册（MVP阶段不需要）
- 消息推送

## 工作流程

1. 你设计并实现 WXML/WXSS/JS
2. 开发者微信开发者工具编译预览
3. 联调后端API
4. 你迭代修改

## 交付标准

- 所有页面在微信开发者工具中可正常编译
- 没有JS报错
- UI视觉统一、干净
- 页面切换流畅、加载有反馈

## 开始工作

从 `miniprogram/pages/index/` 的 WXML+WXSS 开始。
