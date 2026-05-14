# 元HIS 前端开发规范

> 本文档整合自项目 `doc/` 目录下的各规范 HTML 文件，作为统一的 Markdown 版本便于版本管理和 AI 辅助开发。

---

## 目录

1. [项目结构规范](#一项目结构规范)
2. [HTML 规范](#二html-规范)
3. [CSS 规范](#三css-规范)
4. [JavaScript 规范](#四javascript-规范)

---

## 一、项目结构规范

```
project-root/
    |-- css/
    |   |-- common.css           # 全局公共样式
    |   |-- reset.css            # 样式重置
    |-- img/                     # 全局公共图片资源
    |-- js/
    |   |-- plugins/             # 第三方 jQuery 插件
    |   |-- lib/                 # 基础库（jQuery、lodash 等）
    |   |-- utils/               # 工具函数（ajax 封装、表单验证等）
    |-- views/
    |   |-- basic/               # 基础页面（嵌套于 iframe）
    |   |   |-- data_panel/      # 按功能拆分目录
    |   |   |-- plan/            # 按功能拆分目录
    |   |   |   |-- components/  # 私有模块组件（可选）
    |   |   |   |   |-- img/
    |   |   |   |   |-- index.html
    |   |   |   |   |-- script.js
    |   |   |   |   |-- style.css    # 页面私有样式（可选）
    |   |   |-- components/      # 公共组件
    |   |   |   |-- modal.html
    |   |   |   |-- modal.js
    |   |-- screen/              # 大屏
    |   |-- workstation/         # 工作站模式
    |-- .gitignore
    |-- package.json             # 依赖管理（即使不用构建工具）
    |-- README.md
```

---

## 二、HTML 规范

### 1. 【必须】以高保真为主

页面还原度需与设计稿保持一致。

### 2. 【禁止】页面无模块化布局

所有表单元素必须使用语义化容器包裹，禁止元素直接堆叠，禁止使用 `com-label`、`com-input` 等旧类名。

**错误示例：**
```html
<div class="com-label">填制人：</div>
<input class="com-input" name="creator" id="creator" data-bind="value:creator" type="text">
<div class="com-label">审核人：</div>
<input class="com-input" name="auditor" id="auditor" data-bind="value:auditor" type="text">
```

**正确示例：**
```html
<div>
    <label class="vir-label">搜索属性1：</label>
    <input type="text" class="vir-input" placeholder="请在此输入内容">
</div>
<div>
    <label class="vir-label">搜索属性2：</label>
    <input type="text" class="vir-input" placeholder="请在此输入内容">
</div>
```

### 3. 【必须】页面主视口自适应

- 非特定条件不要写死高度，主视口必须撑满可用空间。
- 简单页面：必须做到完全自适应。
- 复杂页面：必须做到不出现错位或遮挡。
- 操作栏因空间不足时，允许加横向滚动条，不允许出现错位。

### 4. 【必须】脚本加载准则

所有 JS 和 CSS 资源统一通过以下方式注入，禁止在 HTML 中直接写 `<script src>` 或 `<link>` 标签加载业务资源：

```javascript
// 当前文件到根目录的路径（下面 js 和 css 的公共路径）
require.serverPath = "../../../";

// 需要注入的 css 路径数组
var stylesheet = ["path/to/file.css"];

// 需要注入的 js 路径数组
var scriptMap = ["path/to/file.js", "path/to/other/file.js"];
```

---

## 三、CSS 规范

### 1. 【禁止】自定义 class 使用 `k-` 前缀

`k-` 为 Kendo UI 保留命名空间，自定义 class 使用该前缀会引发样式冲突。

**错误示例：**
```html
<div class="k-container">...</div>
```

**正确示例：**
```html
<div class="search-container">...</div>
<div class="user-profile__avatar">...</div>
```

### 2. 【禁止】擅自修改公共样式

Kendo UI 的公共样式已存在被污染的情况，修改前必须在团队群内讨论确认。

### 3. 【禁止】无意义地使用 `position: absolute`

滥用 `absolute` 导致元素脱离文档流，后续布局只能用 `margin` 强行撑开空间。

仅在以下场景使用：
- 浮层、徽标、角标等相对父容器定位的元素
- 父容器已明确设置 `position: relative`

### 4. 【推荐】优先使用弹性布局实现自适应

- 一维布局：优先使用 **Flexbox**
- 二维复杂布局：使用 **CSS Grid**
- 避免使用固定像素值定义宽高，优先使用 `flex: 1`、百分比、`fr` 等

```css
/* 推荐 */
.container {
    display: flex;
    flex: 1;
    min-height: 0;
}

/* 禁止 */
.container {
    height: 500px;
}
```

### 5. 【必须】命名规范

- 使用语义化类名，如 `.search-form`、`.user-profile`
- 遵循 **BEM** 命名规范（Block__Element--Modifier）
- 项目自定义工具类统一使用 `vir-` 前缀

### 6. 【禁止】使用以下 CSS 属性

| 属性 | 原因 | 替代方案 |
|------|------|----------|
| `-ms-` 前缀属性（如 `-ms-flex`） | IE 私有属性，已被淘汰 | 使用标准属性 |
| `zoom` | 非标准属性，兼容性差 | `transform: scale()` + `transform-origin` |
| KendoUI 公共 CSS 中过度使用 `>` 直接子选择器 | Kendo UI 新版 DOM 层级有变化，`>` 导致样式不适配 | 改用后代选择器（空格） |

**KendoUI 选择器写法示例：**
```css
/* 不推荐 */
.k-tabstrip > .k-tabstrip-items > .k-item { }

/* 推荐 */
.k-tabstrip .k-tabstrip-items .k-item { }
```

---

## 四、JavaScript 规范

### 1. 【必须】页面整体结构遵循元HIS前端基础架构

所有业务页面统一使用以下对象结构，`invented` 替换为当前页面业务名称：

```javascript
// 定义全局对象（invented 替换为当前页面对象名）
var invented = {} || invented;

// 实体/模型
invented.model = {};

// 数据持久化对象（Kendo DataSource）
invented.dataSource = {
    source1: new kendo.data.DataSource({}),
    source2: new kendo.data.DataSource({}),
};

// 初始化模块
invented.init = {
    target: function () {},   // 初始化控件
    render: function () {},   // 控件事件绑定
    created: function () {}   // 页面构造完成
};

// 业务方法模块（可按业务拆分多个 event2、event3...）
invented.event = {
    func1: function () {},
    func2: function () {}
};

// 页面入口：使用 Promise 链保证初始化顺序
$(function () {
    new Promise(resolve => {
        // 处理页面权限、页面缓存
        return resolve("ok");
    }).then(res => {
        invented.init.target();
    }).then(res => {
        invented.init.render();
    }).then(res => {
        invented.init.created();
    });
});

// 页面卸载：清理所有事件和定时器，避免内存泄漏和重复绑定
window.onbeforeunload = function () {
    $(window).off('resize');
    $(window).off('scroll');
    clearInterval(timer);
    clearTimeout(timeoutId);
};
```

### 2. 【必须】函数命名采用驼峰命名法

以 **动词 + 名词** 形式命名：

```javascript
// 推荐
function getPlanList() {}
function addPlan() {}
function deleteRecord() {}
function updateStatus() {}

// 不推荐
function plan() {}
function doSomething() {}
```

### 3. 【推荐】高频操作添加防抖机制

以下场景必须添加防抖：
- 数据新增操作（防止重复提交）
- Kendo Grid 的 `change` 事件
- 搜索框输入触发请求

```javascript
// 使用 lodash 的 _.debounce
var debouncedSearch = _.debounce(function () {
    invented.event.search();
}, 300);

$("#searchInput").on("input", debouncedSearch);
```

### 4. 【禁止】使用 `setTimeout` 处理时序性问题

`setTimeout` 依赖时间猜测，不可靠且难以维护。时序性问题统一使用 **Promise** 或**回调函数**处理。

**错误示例：**
```javascript
setTimeout(function () {
    invented.init.render();
}, 500);
```

**正确示例：**
```javascript
new Promise(resolve => {
    invented.init.target();
    resolve();
}).then(() => {
    invented.init.render();
});
```
