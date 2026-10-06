# UI 设计系统

本项目的全部视觉规则集中在 **`src/style.css`**。这份文档说明它有哪些 token、怎么用、以及为什么这么定。

设计方向：**深色玻璃质感（科技感）**。基调是深蓝黑底 + 品牌青紫渐变 + 半透明玻璃容器。

---

## 一、铁律

1. **不硬编码颜色。** 一律写 `var(--de-text-1)` 这样的变量，不写 `#fff`、`#409eff`。
2. **不硬编码字号与圆角。** 用 `var(--de-fs-*)`、`var(--de-r-*)`。
3. **改样式先想「这是不是要加一个 token」**，而不是就地写个值。
4. 只有 `style.css` 里允许出现颜色字面量。**判断标准：在其他文件里搜索 `#` 后面跟 3~8 位十六进制的应该搜不到。**
5. 需要给 Element Plus 组件加样式时用 `:deep(...)`，并且优先改 CSS 变量而不是覆盖具体属性。
6. **注意内联样式优先级。** 例如表格的 `header-cell-style="{ background: '#f5f7fa' }"` 是内联样式，优先级高于全局 CSS —— 换主题时必须一起改，否则会出现浅色底压在深色界面上。本项目已把这类内联值也换成了 `var(--de-*)`。

---

## 二、设计 token 清单

### 品牌色

| Token | 值 | 用途 |
|---|---|---|
| `--de-primary` | `#22d3ee` | 主色（青）。链接、选中态、图标 |
| `--de-primary-2` | `#6366f1` | 渐变副色（蓝紫）。与主色组合成按钮渐变 |
| `--de-primary-lite` | `#4dddf6` | 主色 hover 亮色 |
| `--de-primary-2-lite` | `#7b7df5` | 副色 hover 亮色 |
| `--de-primary-strong` | `#0ea5bd` | 主色加深，用于 hover 文字 |
| `--de-primary-soft` | `rgba(34,211,238,.12)` | 主色淡底（选中行、提示块） |
| `--de-primary-line` | `rgba(34,211,238,.30)` | 主色描边 |
| `--de-on-primary` | `#04212b` | 品牌色之上的文字（深色，保证对比度） |
| `--de-glow` | `0 2px 16px rgba(34,211,238,.32)` | 品牌光晕（用在主按钮、品牌图标） |

### 表面层级（越靠上层越亮）

| Token | 值 | 用途 |
|---|---|---|
| `--de-bg` | `#0b1020` | 应用底色 |
| `--de-surface-1` | `rgba(255,255,255,.055)` | 卡片 |
| `--de-surface-2` | `rgba(255,255,255,.035)` | 次级容器、表格行、拖拽区 |
| `--de-surface-solid` | `#101728` | 需要不透明的地方（弹窗） |
| `--de-sidebar` | `rgba(255,255,255,.035)` | 侧边栏 |

### 描边与文字

| Token | 值 | 用途 |
|---|---|---|
| `--de-border` | `rgba(255,255,255,.10)` | 常规分隔线 |
| `--de-border-strong` | `rgba(255,255,255,.16)` | 需要强调的描边（拖拽区虚线） |
| `--de-text-1` | `#f2f5fa` | 标题 / 主要文字 |
| `--de-text-2` | `#a7b0c0` | 正文 / 次要文字 |
| `--de-text-3` | `#77808f` | 辅助 / 禁用 |

### 语义色

`--de-success` `#34d399`　`--de-danger` `#f87171`　`--de-warning` `#fbbf24`

### 字号阶

刻度对齐项目实际用量与 Element Plus 约定，所以组件样式能**无损**收敛，不必取近似值。

| Token | 值 | 用途 |
|---|---|---|
| `--de-fs-1` | `12px` | 辅助信息 |
| `--de-fs-2` | `13px` | 次要文字 |
| `--de-fs-3` | `14px` | 正文（基准） |
| `--de-fs-4` | `16px` | 小标题 |
| `--de-fs-5` | `18px` | 标题 |
| `--de-fs-6` | `20px` | 页面主标题 |
| `--de-fs-7` | `24px` | 特大标题 |

> 例外：图标字形尺寸（如 `.upload-icon` 的 `46px`）属于图形尺寸而非排版字号，不纳入字号阶。

### 圆角阶

| Token | 值 | 用途 |
|---|---|---|
| `--de-r-xxs` | `4px` | 标签、徽章 |
| `--de-r-xs` | `6px` | 小控件 |
| `--de-r-sm` | `8px` | 按钮、输入框、列表项 |
| `--de-r-md` | `12px` | 卡片、面板 |
| `--de-r-lg` | `16px` | 弹窗、大容器 |

### 间距阶

主刻度是 4 的倍数：

`--de-s1` `4px`　`--de-s2` `8px`　`--de-s3` `12px`　`--de-s4` `16px`
`--de-s5` `20px`　`--de-s6` `24px`　`--de-s7` `32px`　`--de-s8` `40px`

> **已知的未完成项**：间距只迁移了落在 4px 网格上的部分（约占 57%）。剩下的是
> Element Plus 组件自身沿用的紧凑值（`6px` / `10px`）以及少量微调值（`2px`）。
> 强行把它们吸附到 `8px` / `12px` 会让所有页面变松，且可能撑破现有布局，
> 因此**有意保留为字面量**。如果后续要统一，正确做法是先把 `6px` / `10px`
> 作为「紧凑间距」补进刻度，再迁移。

### 阴影

`--de-shadow-1`（贴地）　`--de-shadow-2`（卡片）　`--de-shadow-3`（弹窗）

---

## 三、Element Plus 主题覆盖

`main.js` 里做了两件事：

```js
import 'element-plus/theme-chalk/dark/css-vars.css'  // 引入深色变量
document.documentElement.classList.add('dark')       // 挂上 html.dark
```

然后在 `style.css` 的 `html.dark { ... }` 里覆盖：

- `--el-color-primary` 及其 `light-3/5/7/8/9`、`dark-2` 整条色阶
- `--el-color-success / danger / warning / info` 同样整条色阶
- `--el-bg-color*`、`--el-text-color-*`、`--el-border-color-*`、`--el-fill-color-*`
- `--el-border-radius-base / small`

> **为什么要连 `light-N` 一起覆盖？** 深色模式下 Element Plus 的 `light-N` 是
> **往背景方向变暗**（不是变亮）。只改 `--el-color-primary` 而不管派生色阶，
> hover / plain / disabled 等状态就会退回出厂蓝。

---

## 四、怎么换肤

只改 `src/style.css` 里 `:root` 的 `--de-*` 和 `html.dark` 的 `--el-*`，全站生效，**不需要动任何组件**。

---

## 五、本系统顺带修掉的坑（记录一下，避免再踩）

| 现象 | 根因 |
|---|---|
| 页面底部内容被挤出视口 | 全局缺 `box-sizing: border-box`，「高度 100% + padding」溢出 |
| 深色主题下表格表头仍是浅灰底 | 模板里的内联 `header-cell-style`，内联优先级高于全局 CSS |
| 长弹窗底部按钮点不到 | `--el-dialog-margin-top` 默认 15vh 过大且正文不滚动 |
| 文字按钮被涂成渐变胶囊 | 全局 `.el-button--primary` 没有排除 `.is-text` / `.is-plain` |
| 主题色不统一 | 原来全项目有 100+ 处硬编码的 Element Plus 出厂调色板 |
