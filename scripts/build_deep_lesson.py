#!/usr/bin/env python3
"""Build one complete, source-covered learning lesson at a time.

The short first-pass notes remain reproducible in ``build_learning_notes.py``.
This script is the completion path: it combines the lesson-specific editorial
model with the complete source teaching sequence, while removing source-page
artifacts, promotional copy, watermark language and interview-only framing.
"""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

from learning_specs import SPECS


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "content"
OUTPUT_DIR = ROOT / "learning"
OVERRIDE_DIR = ROOT / "scripts" / "lesson_overrides"


HEADING_RENAMES = {
    "前置知识": "先把机制拆开",
    "面试准备": "把知识转成可验证的工程判断",
    "亮点方案": "进一步推导：怎样把机制用进真实系统",
    "面试思路总结": "本节原始知识线索收束",
    "课后讨论（PDF 原文）": "补充讨论与边界校准",
    "思考题": "继续推演",
}

PHRASE_REWRITES = (
    ("面试官", "技术评审者"),
    ("面试者", "学习者"),
    ("候选者", "学习者"),
    ("面试题", "工程问题"),
    ("面试思路", "技术推理路径"),
    ("面试准备", "工程表达准备"),
    ("面试", "技术讨论"),
    ("必考点", "核心知识点"),
    ("必考", "经常需要解释"),
    ("必问", "经常需要解释"),
    ("必面", "经常需要解释"),
    ("刷出亮点", "给出有证据的判断"),
    ("亮点", "进阶推导"),
    ("钓鱼", "预留追问入口"),
    ("鱼饵", "追问入口"),
    ("骚操作", "定制化做法"),
    ("SAO 操作", "定制化做法"),
    ("答题", "技术说明"),
    ("回答", "解释"),
    ("刮目相看", "理解这套推理的价值"),
)

OFFICIAL_REFS = {
    "02-load-balancing": [
        ("NGINX · HTTP Load Balancing", "https://docs.nginx.com/nginx/admin-guide/load-balancer/http-load-balancer/"),
        ("gRPC · Load Balancing", "https://grpc.io/blog/grpc-load-balancing/"),
    ],
    "03-circuit-breaker": [
        ("Resilience4j · CircuitBreaker", "https://resilience4j.readme.io/docs/circuitbreaker"),
        ("Resilience4j · Metrics and events", "https://resilience4j.readme.io/docs/getting-started-3"),
    ],
    "04-degradation": [
        ("Spring Cloud CircuitBreaker · Reference", "https://docs.spring.io/spring-cloud-circuitbreaker/reference/"),
        ("Resilience4j · Getting Started", "https://resilience4j.readme.io/docs/getting-started"),
    ],
    "05-rate-limiting": [
        ("Resilience4j · RateLimiter", "https://resilience4j.readme.io/docs/ratelimiter"),
    ],
    "06-isolation": [
        ("Resilience4j · Bulkhead", "https://resilience4j.readme.io/docs/bulkhead"),
    ],
    "07-timeout-control": [
        ("Resilience4j · TimeLimiter", "https://resilience4j.readme.io/docs/timeout"),
    ],
    "08-third-party-calls": [
        ("Resilience4j · Retry", "https://resilience4j.readme.io/docs/retry"),
        ("Resilience4j · TimeLimiter", "https://resilience4j.readme.io/docs/timeout"),
    ],
    "09-service-governance": [
        ("Resilience4j · Getting Started", "https://resilience4j.readme.io/docs/getting-started"),
        ("Resilience4j · Spring Boot configuration", "https://resilience4j.readme.io/docs/getting-started-3"),
    ],
    "09a-mock-service-governance": [
        ("OpenTelemetry · Traces", "https://opentelemetry.io/docs/concepts/signals/traces/"),
        ("Prometheus · Querying basics", "https://prometheus.io/docs/prometheus/latest/querying/basics/"),
    ],
    "10-mysql-index": [
        ("MySQL 8.4 · Multiple-Column Indexes", "https://dev.mysql.com/doc/refman/8.4/en/multiple-column-indexes.html"),
        ("MySQL 8.4 · Clustered and Secondary Indexes", "https://dev.mysql.com/doc/refman/8.4/en/innodb-index-types.html"),
    ],
    "11-sql-optimization": [
        ("MySQL 8.4 · EXPLAIN", "https://dev.mysql.com/doc/refman/8.4/en/explain.html"),
        ("MySQL 8.4 · Optimizer Use of Generated Column Indexes", "https://dev.mysql.com/doc/refman/8.4/en/generated-column-index-optimizations.html"),
    ],
    "12-database-locks": [
        ("MySQL 8.4 · InnoDB Locking", "https://dev.mysql.com/doc/refman/8.4/en/innodb-locking.html"),
        ("MySQL 8.4 · Deadlocks", "https://dev.mysql.com/doc/refman/8.4/en/innodb-deadlocks.html"),
    ],
    "13-mvcc": [
        ("MySQL 8.4 · Multi-Versioning", "https://dev.mysql.com/doc/refman/8.4/en/innodb-multi-versioning.html"),
        ("MySQL 8.4 · Consistent Nonlocking Reads", "https://dev.mysql.com/doc/refman/8.4/en/innodb-consistent-read.html"),
    ],
    "14-database-transactions": [
        ("MySQL 8.4 · Redo Log", "https://dev.mysql.com/doc/refman/8.4/en/innodb-redo-log.html"),
        ("MySQL 8.4 · Binary Log", "https://dev.mysql.com/doc/refman/8.4/en/binary-log.html"),
    ],
    "数据库": [
        ("MySQL 8.4 Reference Manual", "https://dev.mysql.com/doc/refman/8.4/en/"),
        ("MySQL 8.4 · InnoDB", "https://dev.mysql.com/doc/refman/8.4/en/innodb-storage-engine.html"),
    ],
    "消息队列": [
        ("Apache Kafka · Documentation", "https://kafka.apache.org/documentation/"),
        ("Apache Kafka · Design", "https://kafka.apache.org/25/design/design/"),
    ],
    "缓存": [
        ("Redis · Documentation", "https://redis.io/docs/latest/"),
        ("Redis · Key eviction", "https://redis.io/docs/latest/develop/reference/eviction/"),
    ],
    "NoSQL": [
        ("Elasticsearch · Distributed architecture", "https://www.elastic.co/docs/deploy-manage/distributed-architecture/clusters-nodes-shards"),
        ("MongoDB · Manual", "https://www.mongodb.com/docs/manual/"),
    ],
}

FACT_CALIBRATIONS = {
    "03-circuit-breaker": (
        "以当前 Resilience4j 文档为例，关闭态既可以使用按调用次数统计的滑动窗口，也可以使用按时间统计的滑动窗口；"
        "失败率或慢调用率都要在达到最小样本数以后才有资格触发状态切换。打开态等待结束后进入半开态时，只允许配置数量的探测调用，"
        "其余调用继续被拒绝。这里校准的是一种具体实现：不要把课程中的“固定等一分钟”误认为熔断器唯一的恢复算法，也不要把某个版本默认值当作通用建议。"
    ),
    "04-degradation": (
        "容错库可以在异常或拒绝时调用 fallback，但库无法替业务决定 fallback 的语义。读请求返回旧缓存、写请求返回“已受理”、"
        "或者直接失败是三种不同承诺；只有业务状态机和补偿流程能说明哪一种安全。"
    ),
    "05-rate-limiting": (
        "不同实现的计数方式不同。Resilience4j 当前官方实现按刷新周期发放许可，并不等同于课程中用于解释突发流量的令牌桶。"
        "因此要区分“限流目的、理论算法、所用库的实际实现”三层，不能看到 RateLimiter 名称就假定它一定有令牌积累能力。"
    ),
    "06-isolation": (
        "Resilience4j 官方区分基于信号量的并发隔离和带有界队列、固定线程池的线程池隔离。两者都只能约束进入该隔离舱的并发；"
        "若多个隔离舱最终共享同一个已饱和数据库，底层故障域仍没有被真正切开。"
    ),
    "07-timeout-control": (
        "TimeLimiter 可以对 Future 或 CompletionStage 设置等待边界，并可配置是否调用取消；但发出 cancel 不代表任意网络、数据库或业务代码都已停止。"
        "真实系统仍需把截止时间和取消信号传给下游，并验证超时后的残留工作。"
    ),
    "08-third-party-calls": (
        "Resilience4j Retry 允许按返回结果、异常类型和尝试次数决定是否重试；官方配置里的最大尝试次数包含首次调用。"
        "这只是调用策略，不会自动赋予写操作幂等性。第三方写请求在重试前仍必须有幂等键、状态查询或补偿协议。"
    ),
    "09-service-governance": (
        "熔断、重试、限流、超时和隔离可以叠加，但执行顺序会改变统计口径、资源消耗和最终错误语义。"
        "框架注解的默认顺序属于具体实现事实；架构设计必须先明确希望谁包住谁，再用测试和指标验证。"
    ),
    "09a-mock-service-governance": (
        "故障分析里的日志、指标和链路追踪是互补证据：指标说明异常从何时开始、影响多大，链路追踪定位慢或错在哪一跳，日志解释该跳内部发生了什么。"
        "工具只能提供观测记录，根因仍需要通过时间线、对照实验和修复后的指标回落来证明。"
    ),
    "10-mysql-index": (
        "MySQL 8.4 官方文档仍明确复合索引可用于其最左前缀，但是否真正选择该索引由优化器根据代价决定。"
        "“符合最左前缀”只表示具备索引查找能力，不等于一定零回表、一定覆盖查询或一定比全表扫描快。"
    ),
    "11-sql-optimization": (
        "EXPLAIN 展示优化器计划；EXPLAIN ANALYZE 会真实执行语句，并给出迭代器的估算、实际行数、循环次数和时间。"
        "因此生产写语句不能在不了解副作用时直接运行 ANALYZE，且一次执行计划也不能替代不同参数分布下的观测。"
    ),
    "12-database-locks": (
        "InnoDB 的加锁对象与访问到的索引记录和范围有关，不应把所有 UPDATE 简化成“只锁最终返回的行”。"
        "官方文档也要求应用处理死锁受害事务并按业务语义重试；数据库能回滚一个事务，不会替应用恢复外部副作用。"
    ),
    "13-mvcc": (
        "MySQL 8.4 的一致性非锁定读会根据隔离级别选择快照；旧版本通过 undo 信息重建。"
        "这与 SELECT FOR UPDATE 等锁定读不同。MVCC 减少普通读写互斥，但更新、删除和锁定读仍参与锁竞争。"
    ),
    "14-database-transactions": (
        "redo、binlog、数据页和副本确认是不同耐久边界。MySQL 返回提交成功后能承受哪些故障，取决于日志刷盘参数、存储栈和复制确认策略；"
        "不能把一次 COMMIT 泛化成跨主机、跨机房和跨备份的绝对不丢。"
    ),
}


def yaml_string(value: str) -> str:
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def mermaid(flow: list[str]) -> str:
    nodes = [f'    S{i}["{i}. {label.replace(chr(34), chr(39))}"]' for i, label in enumerate(flow, 1)]
    links = [f"    S{i} --> S{i + 1}" for i in range(1, len(flow))]
    return "\n".join([
        "flowchart TD",
        *nodes,
        *links,
        "    classDef start fill:#e8f1ff,stroke:#2878d0,color:#183153",
        "    classDef finish fill:#e6f6ef,stroke:#2c8c69,color:#153f33",
        "    class S1 start",
        f"    class S{len(flow)} finish",
    ])


def source_body(lesson_id: str) -> tuple[int, str]:
    path = SOURCE_DIR / f"{lesson_id}.md"
    raw = path.read_text(encoding="utf-8")
    pages = re.search(r"^source_pages:\s*(\d+)\s*$", raw, re.MULTILINE)
    if not pages:
        raise ValueError(f"{path} 缺少 source_pages")
    body = re.sub(r"\A---\n[\s\S]*?\n---\n", "", raw)
    marker = "## PDF 原文"
    if marker in body:
        body = body.split(marker, 1)[1]
    lesson_number = re.match(r"\d+", lesson_id)
    if lesson_number:
        duplicate = re.search(
            rf"(?m)^###\s+{re.escape(lesson_number.group())}｜([^\n]*)\n",
            body,
        )
        if duplicate:
            title_fragment = duplicate.group(1).strip()
            body = body[:duplicate.start()] + body[duplicate.end():]
            if not re.search(r"[？?。！!]$", title_fragment):
                body = re.sub(r"(?m)^\s*###\s+[^\n#]{1,12}\n", "", body, count=1)
    return int(pages.group(1)), body


def clean_source_walkthrough(raw: str) -> str:
    """Keep teaching substance in order while deleting conversion artifacts."""

    raw = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw)
    lines: list[str] = []
    skip_editorial_bridge = False
    for original in raw.splitlines():
        line = original.strip()
        if not line:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        if line.startswith("<!-- source-page:") or re.fullmatch(r"!\[[^]]*]\([^)]*\)", line):
            continue
        if "版权归" in line or "防盗追踪" in line or "未经许可" in line:
            continue
        if any(token in line for token in ("97kt", "xingkeit", "优质IT", "防断更")):
            continue
        if line.startswith("## 学习前补齐"):
            skip_editorial_bridge = True
            continue
        if skip_editorial_bridge:
            if line == "---":
                skip_editorial_bridge = False
            continue
        if line == "---" or line.startswith("> 课程：") or line.startswith("> 来源："):
            continue
        if line.startswith("# "):
            continue
        if re.match(r"^(全部留言|最新\s+精选|共\s*\d+\s*条评论)", line):
            continue
        if re.match(r"^[^\s]{1,24}\s*20\d{2}-\d{2}-\d{2}\s+来自", line):
            line = re.sub(r"^[^\s]{1,24}\s*20\d{2}-\d{2}-\d{2}\s+来自[^\s]+", "补充讨论：", line)
        line = re.sub(r"[]+", "", line)
        line = re.sub(r"^作者回复\s*:\s*", "讲解补充：", line)
        line = re.sub(r"^作者回复\s*", "讲解补充：", line)
        line = re.sub(r"^###\s+(.+)$", lambda m: "### " + HEADING_RENAMES.get(m.group(1), m.group(1)), line)
        line = re.sub(r"^##\s+(.+)$", lambda m: "### " + HEADING_RENAMES.get(m.group(1), m.group(1)), line)
        for old, new in PHRASE_REWRITES:
            line = line.replace(old, new)
        line = line.replace("大明", "讲解者")
        line = re.sub(r"^你好，我是讲解者。", "", line)
        line = line.replace("今天我们来聊一聊", "本节讨论")
        line = line.replace("今天我们来聊", "本节讨论")
        line = line.replace("所以今天我就来给你介绍一下", "因此需要继续考察")
        line = line.replace("下面我先来给你介绍", "下面先介绍")
        line = line.replace("接下来我带你一个个看", "下面逐一拆解")
        line = line.replace("你可能想到", "这里首先要考虑")
        line = line.replace("你可能会觉得", "常见疑问是")
        line = line.replace("你可能觉得", "常见疑问是")
        line = line.replace("你可以看到", "由此可以看到")
        line = line.replace("我前面和你提到过", "前面已经提到")
        line = line.replace("我前面提到过", "前面已经提到")
        line = line.replace("我前面提到", "前面提到")
        line = line.replace("我这里稍微给你解释一下", "这里需要解释")
        line = line.replace("这里我可以用", "这里可以用")
        line = line.replace("我们公司", "某个线上系统")
        line = line.replace("你可以这么说", "可以把方案整理为")
        line = line.replace("你就可以这样解释", "可以这样解释")
        line = line.replace("在技术讨论的时候", "在工程复盘时")
        line = line.replace("技术讨论和汇报晋升", "技术评审")
        line = line.replace("技术评审者进一步问", "后续继续追问")
        line = re.sub(r"欢迎你把[^。！!]*[。！!]?$", "", line)
        line = re.sub(r"我们下节课再见[！!。]?$", "", line)
        line = re.sub(r"相信[^。]*技术评审者[^。]*[。]?$", "", line)
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)

    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def build_deep_note(spec: dict) -> str:
    pages, raw_source = source_body(spec["id"])
    walkthrough = clean_source_walkthrough(raw_source)
    flow = spec["flow"]
    question, answer = spec["check"]
    flow_rows = "\n".join(
        f"| {i} | {item} | {flow[i] if i < len(flow) else '得到可核对的终态'} |"
        for i, item in enumerate(flow, 1)
    )
    evidence_rows = "\n".join(
        f"| {i} | {item} | 开始时间、结束时间、输入标识、结果状态、异常原因 |"
        for i, item in enumerate(flow, 1)
    )
    arc = "\n".join(f"{i}. {item}" for i, item in enumerate(spec["arc"], 1))
    first = flow[0]
    last = flow[-1]
    refs = OFFICIAL_REFS.get(spec["id"], OFFICIAL_REFS.get(spec["chapter"], []))
    refs_md = "\n".join(f"- [{label}]({url})" for label, url in refs)
    calibration = FACT_CALIBRATIONS.get(spec["id"], "本课不把某个框架的默认配置当作普遍结论；具体参数需要回到目标版本官方资料和实测数据。")

    return f'''---
id: {yaml_string(spec["id"])}
order: {spec["order"]}
chapter: {yaml_string(spec["chapter"])}
title: {yaml_string(spec["title"])}
source_note: {yaml_string(f"../content/{spec['id']}.md")}
source_pages: {pages}
edition: "independent-learning-exemplar"
walkthrough_flow: {yaml_string('|'.join(flow))}
walkthrough_example: {yaml_string(spec["example"])}
walkthrough_question: {yaml_string(question)}
---

# {spec["title"]}

> 本课只解决一个问题：{spec["question"]}

这不是原页面的缩写，也不是一组孤立结论。下面先建立一个能推演的最小世界，再把状态、数字和失败分支摊开，最后按来源讲解顺序覆盖全部知识线索。读完后，你应当能从 `{first}` 一直解释到 `{last}`，并说明中途任意一步失败会留下什么状态。

## 零基础入口：先建立本课的心智画面

{spec["bridge"]}

先不要急着记组件名。只抓住四个问题：**现在手里有什么输入？下一步只做什么动作？哪个状态发生变化？变化后的结果交给谁？** 之后遇到新框架，只要这四个答案不变，核心机制就没有变。

### 放进一个足够小、可以手算的世界

{spec["example"]}

这个小世界故意只保留本课必需的对象。生产系统会有更多节点、线程、分片和异常，但数量增加不会改变这里的因果关系。先确认你能手算这个例子，再把数字替换成真实系统数据。

### 先预测，不要马上看结论

**{question}**

先写下自己的判断，并指出你依赖的前提。文末自我检查会揭示答案；如果答案不同，回到下面的状态表找出第一个分叉点。

## 本节精讲：让机制一步一步发生

{spec["mechanism"]}

### 可见状态推进

| 当前步 | 现在发生的动作 | 下一步拿到什么 |
| ---: | --- | --- |
{flow_rows}

```mermaid
{mermaid(flow)}
```

图只承担一个任务：让你看清状态如何向前移动。它不意味着每一步必然成功；网络超时、进程退出、重复执行和数据竞争都可能让箭头停在中间，因此后面必须继续讨论失效边界。

### 一次带数字的完整推演

{spec["example"]}

数字不是装饰。它迫使我们回答容量、顺序、时间窗口或版本选择问题。若换一个数字就得出不同结论，真正的设计依据就是那个阈值，而不是某个中间件名称。

## 按讲解顺序重建知识链：完整来源讲解

下面按来源资料的教学顺序重新编排完整内容。转换页码、来源图片、推广信息、水印、角色化问答和只服务于技术讨论场景的话术已经删除；机制、算法、例子、反例、事故线索、评论补充和限制条件仍然保留。这里的作用是补齐知识覆盖，不取代前面的独立推演。

{walkthrough}

## 把完整讲解收束成一条因果链

{arc}

把这几步连接起来时，不要省略“为什么”。最终结论只有在前提、状态变化和失败代价都说得清楚时才可靠。

## 误区与失效边界

{spec["boundary"]}

再加一条通用但必须落实到本课对象上的边界：机制只能处理它看得见的信号。若输入指标失真、状态没有持久化、错误被吞掉，或者补偿没有幂等保护，再成熟的框架也只能基于错误证据作决定。

### 三种故障注入方式

| 故障 | 要观察什么 | 不能接受的解释 |
| --- | --- | --- |
| 在第 2 步前让依赖超时 | 是否停在可重试状态，是否消耗完上游预算 | “框架稍后会处理” |
| 在状态写入后让进程退出 | 重启后能否识别已完成与待继续动作 | “再执行一次应该没事” |
| 对同一输入并发执行两次 | 是否出现重复副作用、顺序颠倒或覆盖 | “概率很低” |

## 工程验证：把理解变成可以复查的证据

{spec["artifact"]}

| 步骤 | 状态或动作 | 最少应留下的证据 |
| ---: | --- | --- |
{evidence_rows}

验证时同时记录成功路径和失败路径。只证明“正常时能跑通”不能说明设计可靠；至少要让一次超时、一次进程退出和一次重复请求可重现，并能根据日志或指标解释最后状态。

## 学完检查：闭卷画出本课

你现在应该能独立完成四件事：

1. 用自己的话说出本课唯一问题，不使用产品名也能解释。
2. 复算上面的具体例子，并指出哪个输入改变会让结论改变。
3. 沿 Mermaid 图注入一次失败，预测系统停在哪里以及由谁收敛。
4. 说出本课机制不保证什么，并给出一个反例。

## 自我检查

<details>
<summary>{html.escape(question)}</summary>

{answer}

</details>

<details>
<summary>怎样证明自己不是只记住了名词？</summary>

把 `{first}` 的一个真实输入写出来，逐步记录到 `{last}`。然后在中间任意一步制造失败；如果你能解释当前状态、下一责任方、可观测证据和恢复边界，就已经拥有可以迁移的工程模型。

</details>

## 来源与事实校准

- [查看完整来源稿（本地 {pages} 页资料）](../content/{spec['id']}.md)

### 当前事实校准

{calibration}

{refs_md}

来源稿用于核对覆盖范围，不随公开站点发布。产品默认值和具体内部行为可能随版本变化；落地时应使用目标版本的官方文档、可运行实验和故障演练校准。本学习稿中的零基础入口、状态推演、故障矩阵和工程验证属于编辑补充，不冒充来源讲解者的原话。
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lesson_id", help="one lesson id, for example 02-load-balancing")
    args = parser.parse_args()
    specs = {spec["id"]: spec for spec in SPECS}
    if args.lesson_id not in specs:
        raise SystemExit(f"unknown lesson id: {args.lesson_id}")

    spec = specs[args.lesson_id]
    note = build_deep_note(spec)
    output = OUTPUT_DIR / f"{args.lesson_id}.md"
    override = OVERRIDE_DIR / output.name
    output.write_text(note, encoding="utf-8")
    override.write_text(note, encoding="utf-8")
    print(f"built deep lesson {args.lesson_id}: {len(note)} chars, {len(note.splitlines())} lines")


if __name__ == "__main__":
    main()
