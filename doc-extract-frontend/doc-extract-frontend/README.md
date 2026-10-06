# 文档提取系统 · 前端

把「目标文档」里的信息按「模板表头」抽取出来，再回填进模板文件导出。

大语言模型的调用在后端（同仓库的 `doc-system-backend`），本目录只负责界面与交互。

> 这份 README 之前是 Vite 脚手架自带的模板文案，一直没改；现已替换为项目真实说明。

---

## 技术栈

| 项 | 版本 / 说明 |
|---|---|
| Vue | 3.5（`<script setup>` 单文件组件） |
| 构建 | Vite 8 |
| UI 组件库 | Element Plus 2（已切换为深色主题并覆盖品牌色） |
| 状态管理 | Pinia（`pinia-plugin-persistedstate` 持久化部分状态） |
| 路由 | Vue Router 5 |

## 本地运行

需要后端先监听 `127.0.0.1:8000`（开发服务器会把 `/api` 代理过去，见 `vite.config.js`）。

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # 产物输出到 dist/
npm run preview    # 预览构建产物
```

## 目录结构

```
src/
├── api/            与后端交互的接口封装（按业务分文件）
├── assets/         图片等静态资源
├── components/     可复用组件
│   ├── FileUploadCard.vue      上传卡片（拖拽区 + 已选列表）
│   ├── FileStatusTable.vue     文件解析状态表格
│   ├── StepBar.vue             顶部四步流程条
│   ├── FieldSettingDialog.vue  字段设置弹窗
│   ├── TaskDetailDialog.vue    历史任务详情弹窗
│   └── DocumentPreview.vue     正文预览
├── stores/         Pinia 状态（workspace / file / field / result）
├── views/          路由级页面
│   ├── UploadPage.vue    ① 上传文档
│   ├── ExtractPage.vue   ② 设置字段
│   ├── ResultPage.vue    ③ 核对结果
│   ├── ExportPage.vue    ④ 导出文件
│   └── SchemePage.vue    方案管理
├── style.css       ★ 设计系统（唯一风格来源）
└── main.js         应用入口
```

## UI 设计系统

全站样式集中在 **`src/style.css`**，由三部分组成：

1. **设计 token** —— 配色 / 字号 / 间距 / 圆角 / 阴影，全部是 `--de-*` 变量
2. **Element Plus 主题覆盖** —— 主色与语义色整系列换成品牌色系
3. **全局基础样式与共享类**

> **写新页面时的铁律：不要硬编码颜色、字号、圆角。**
> 一律引用 `var(--de-*)`。换肤只需要改 `style.css` 一个文件。

完整的 token 清单与使用规则见 **[docs/ui-design-system.md](docs/ui-design-system.md)**。

## 协作流程

- `main` 只放能跑起来的版本，**任何人都不直接在上面改**
- 从当前的功能分支开自己的分支：`git switch -c feat/xxx`
- 改完 `git push`，在 GitHub 上开 PR 让队友 review 后再合并
- 提交信息用前缀：`feat:` / `fix:` / `style:` / `refactor:` / `docs:` / `chore:`
