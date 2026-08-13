#!/usr/bin/env python3
"""Build the independent learning edition from topic-specific editorial specs."""

from __future__ import annotations

import html
import re
import shutil
from pathlib import Path

from learning_specs import SPECS


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "content"
OUTPUT_DIR = ROOT / "learning"
OVERRIDE_DIR = ROOT / "scripts" / "lesson_overrides"


OFFICIAL_REFS = {
    "数据库": [
        ("MySQL 8.4 · InnoDB 存储引擎", "https://dev.mysql.com/doc/refman/8.4/en/innodb-storage-engine.html"),
        ("MySQL 8.4 · 锁定读", "https://dev.mysql.com/doc/refman/8.4/en/innodb-locking-reads.html"),
        ("MySQL 8.4 · Redo Log", "https://dev.mysql.com/doc/refman/8.4/en/innodb-redo-log.html"),
    ],
    "消息队列": [
        ("Apache Kafka · 官方文档", "https://kafka.apache.org/documentation/"),
        ("Apache Kafka · Design", "https://kafka.apache.org/25/design/design/"),
    ],
    "缓存": [
        ("Redis · EXPIRE", "https://redis.io/docs/latest/commands/expire/"),
        ("Redis · Key eviction", "https://redis.io/docs/latest/develop/reference/eviction/"),
        ("Redis · Distributed locks", "https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/"),
        ("Redis · Diagnosing latency issues", "https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/latency/"),
    ],
    "NoSQL": [
        ("Elasticsearch · Clusters, nodes and shards", "https://www.elastic.co/docs/deploy-manage/distributed-architecture/clusters-nodes-shards"),
        ("MongoDB · Replication", "https://www.mongodb.com/docs/manual/replication/"),
        ("MongoDB · Sharded cluster components", "https://www.mongodb.com/docs/manual/core/sharded-cluster-components/"),
        ("MongoDB · ESR guideline", "https://www.mongodb.com/docs/manual/tutorial/equality-sort-range-guideline/"),
    ],
}


def source_metadata(lesson_id: str) -> tuple[int, str]:
    path = SOURCE_DIR / f"{lesson_id}.md"
    raw = path.read_text(encoding="utf-8")
    pages_match = re.search(r'^source_pages:\s*(\d+)\s*$', raw, re.MULTILINE)
    if not pages_match:
        raise ValueError(f"{path} 缺少 source_pages")
    return int(pages_match.group(1)), path.name


def yaml_string(value: str) -> str:
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def mermaid(flow: list[str]) -> str:
    nodes = []
    for index, label in enumerate(flow, start=1):
        escaped = label.replace('"', "'")
        nodes.append(f'    N{index}["{index}. {escaped}"]')
    links = [f"    N{index} --> N{index + 1}" for index in range(1, len(flow))]
    return "\n".join([
        "flowchart TD",
        *nodes,
        *links,
        "    classDef start fill:#e8f1ff,stroke:#2878d0,color:#183153",
        "    classDef finish fill:#e6f6ef,stroke:#2c8c69,color:#153f33",
        "    class N1 start",
        f"    class N{len(flow)} finish",
    ])


def calibration_links(chapter: str, lesson_id: str) -> list[tuple[str, str]]:
    if chapter == "缓存":
        if lesson_id == "31-redis-expiration":
            return OFFICIAL_REFS[chapter][:1]
        if lesson_id == "32-cache-eviction":
            return OFFICIAL_REFS[chapter][1:2]
        if lesson_id == "36-redis-single-thread":
            return OFFICIAL_REFS[chapter][3:]
        if lesson_id == "37-redis-distributed-lock":
            return OFFICIAL_REFS[chapter][2:3]
        return OFFICIAL_REFS[chapter][1:3]
    return OFFICIAL_REFS.get(chapter, [])


def build_note(spec: dict) -> str:
    source_pages, source_name = source_metadata(spec["id"])
    flow = spec["flow"]
    question, answer = spec["check"]
    arc = "\n".join(f"{index}. {item}" for index, item in enumerate(spec["arc"], start=1))
    state_rows = "\n".join(
        f"| {index} | {item} | 记录耗时、结果与异常分支，确认状态能进入下一步 |"
        for index, item in enumerate(flow, start=1)
    )
    refs = calibration_links(spec["chapter"], spec["id"])
    refs_md = "\n".join(f"- [{label}]({url})" for label, url in refs)
    if refs_md:
        refs_md = f"\n\n本课涉及的产品行为以这些官方资料为校准入口：\n\n{refs_md}"

    return f'''---
id: {yaml_string(spec["id"])}
order: {spec["order"]}
chapter: {yaml_string(spec["chapter"])}
title: {yaml_string(spec["title"])}
source_note: {yaml_string(f"../content/{source_name}")}
source_pages: {source_pages}
edition: "independent-learning"
---

# {spec["title"]}

> 本课只回答一个问题：{spec["question"]}

这是一份独立学习稿。来源资料用于核对知识范围；下面的解释、推演、边界和图示均按工程学习路径重新组织，不依赖原页面也能完整阅读。

## 先补齐：建立正确的心智模型

{spec["bridge"]}

读这一课时，始终把“组件名字”换成三个可追踪对象：**谁发起动作、状态存在哪里、失败后由谁收敛**。这样遇到不同产品或版本，仍能用同一套模型判断。

## 本节精讲：机制是怎样一步步工作的

{spec["mechanism"]}

下面这张图只表达本课最重要的状态推进，蓝色是入口，绿色是可验收的终点；任一箭头失败，都要回到上文寻找重试、回退或人工处理的位置。

```mermaid
{mermaid(flow)}
```

### 一次带数字的完整推演

{spec["example"]}

数字的作用不是制造精确感，而是暴露容量和时间关系。把例子中的流量、延迟、分片数或版本号替换成自己的真实数据，方案可能会随之改变。

## 误区与失效边界

{spec["boundary"]}

判断一个结论是否可靠，可以追问两次：**它依赖什么前提？前提失效后系统留下了什么状态？** 如果回答只能停在“框架会自动处理”，就还没有走到工程边界。

## 按讲解顺序重建知识链

来源稿覆盖的论证主线在这里被重建成四步，保留问题、推导、反例和收束，不沿用原页面措辞：

{arc}

把四步连起来后，本课不是一个孤立结论，而是一条可以复演的因果链。需要回查课程覆盖范围时，可打开文末的来源稿；学习时以本页模型为主。

## 工程验证：把理解变成证据

{spec["artifact"]}

### 状态检查表

| 步骤 | 状态或动作 | 需要留下的证据 |
| ---: | --- | --- |
{state_rows}

检查表不是要求生产系统逐字采用这些字段，而是强迫设计者为每一步提供可观测结果。只有入口、没有终态的流程，最终都会形成无法解释的中间状态。

## 自我检查

<details>
<summary>{html.escape(question)}</summary>

{answer}

</details>

再做一次闭卷练习：不看上文画出状态图，并为其中任意两个箭头注入超时、进程崩溃或重复请求。如果你能预测最终状态和观测信号，这一课才真正从“听懂”变成“会用”。

## 来源与版本校准

- [查看来源稿（{source_pages} 页资料整理）](../content/{source_name})

来源稿只用于追溯知识范围，不是本学习稿的正文。具体产品的默认值、命令与内部实现会随版本变化；落地前应使用目标版本官方文档和故障演练再次确认。{refs_md}
'''


def main() -> None:
    expected_ids = {path.stem for path in SOURCE_DIR.glob("*.md")}
    spec_ids = {spec["id"] for spec in SPECS}
    if expected_ids != spec_ids:
        missing = sorted(expected_ids - spec_ids)
        extra = sorted(spec_ids - expected_ids)
        raise SystemExit(f"课程规格不完整 missing={missing} extra={extra}")

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    for spec in SPECS:
        output = OUTPUT_DIR / f'{spec["id"]}.md'
        override = OVERRIDE_DIR / output.name
        if override.exists():
            shutil.copyfile(override, output)
        else:
            output.write_text(build_note(spec), encoding="utf-8")

    print(f"built {len(SPECS)} independent learning notes in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
