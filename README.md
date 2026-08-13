# Core Study · 后端工程核心能力

这是一个以 Markdown 为内容源的本地学习网站，页面风格和学习交互沿用 `nlp_study` 的阅读体验。

在线学习地址：[https://luyunix.github.io/core_study/](https://luyunix.github.io/core_study/)

网站默认读取 `learning/` 中的 50 篇学习稿。已完成的章节按问题、心智模型、连续机制推演、失效边界、工程验证和自测进行深度重写；其余文件保留为旧版草稿，等待逐节重写和发布。网站会根据 Markdown 状态实时显示完成数量。`content/` 只作为本地来源层保留，不参与公开站点发布。

## 本地浏览

```bash
pnpm install
pnpm dev
```

打开 `http://127.0.0.1:4173/`。站内支持全文搜索、专题目录、收藏、完成进度和学习稿/来源稿切换，学习状态保存在浏览器本地。

## 工程目录

- `learning/`：50 篇独立学习稿，网站默认数据源
- `content/`：50 篇来源稿及转换图片，仅供交叉核对
- `scripts/learning_specs.py`：每篇学习稿的主题化论证、例子和边界
- `scripts/build_learning_notes.py`：生成独立学习稿
- `scripts/audit_learning_content.py`：检查结构、图示、来源链接与来源痕迹
- `scripts/lesson_overrides/`：逐节完成并经人工验收的深度学习稿
- `examples/`：与课程推演一致、可以直接运行的最小示例
- `src/`：React 阅读站点

## 重建与验证

```bash
pnpm run learning:build
pnpm run audit
pnpm build
```

学习稿审计会核对 50 篇课程一一对应、每篇均有完整推演与自测、不引用来源图片，并拒绝来源水印和旧式问答话术进入学习层。
