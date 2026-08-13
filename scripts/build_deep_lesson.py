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

EDITORIAL_REWRITES = {
    "有的人明明知道有一些问题肯定会被问到，但技术讨论前还是不好好准备，要么解释得模棱两可，要么答非所问，从而错失 offer。有的人不知道怎么包装自己的项目经历，凸显自己解决方案的优点，以至于看上去非常平淡，没办法给人留下深刻印象。还有人简历写得花里胡哨，但是实际上一问三不知，简历和经历完全对不上。": (
        "常见学习失败有三类：对预期问题没有形成完整解释；只描述自己做过什么，却没有给出约束、证据与效果；或者写下了超出真实经验的结论，一追问就无法说明细节。解决办法不是包装，而是把状态、数字、取舍和验证补齐。"
    ),
    "这里还要单独强调一下这门课程的一个特殊的设计——进阶推导方案。虽然技术讨论成功很大程度上取决于你对技术评审者的问题是否能做到对答如流，但别忘了，并不是说你解释出全部问题就能拿到offer，更重要的一点是要比别的学习者解释得更出彩。因此在上述每一个主题之下，我都会教你如何展示自己的进阶推导，期待一下吧。": (
        "只复述标准方案不足以支持工程决策。每个专题都应继续追问适用前提、代价、失败边界和替代方案，再用真实指标或最小实验说明为什么当前选择更合适。"
    ),
    "当然不是，我在课程中展示的所有案例都是我在工作场景中摸爬滚打多年摸索出来的，可以说这门课程是来自于实践，最终也将回归实践。所有的案例和方案都是可以拿到生产环境中去实践的。": (
        "案例的价值在于回到实践中验证。不过生产环境的版本、规模和业务约束不同，不能直接照搬；应先缩成最小实验，再通过压测、灰度和故障演练逐步校准。"
    ),
    "如果你是工作不久，经验不足的小白，可以把前面的知识点当作台阶，把里面的最佳实践作为样板，去大刀阔斧地应用在实际的生产环境中。如果你已经有了一些基础和经验，就可以通过前面系统的知识夯实自己的基础，通过里面的进阶推导方案，为自己目前的工作找到新的解决思路。如果你正准备跳槽，那这门课程可以说是为你量身打造的了，它将成为你的助手，帮你快速搭建起自己的知识框架，助你技术讨论通关。": (
        "零基础学习者先用小例子建立状态模型，有经验的学习者则应把同一模型映射到自己的链路，比较现状与备选方案。无论处于哪个阶段，都不要直接在生产环境大幅改动，而要从可回滚实验开始。"
    ),
    "工作中的重难点也必然会成为技术讨论中的常考点，所以我们这门课程也并不是只会教你技术讨论的套路，更多的是技术之间的联系、灵活多变的方案、处理问题的思路，以及沟通时的引导策略。如果你可以透过表面的知识点和技术讨论的话术，掌握这些更深层次的技能，那么你收获的就不只是一两个 offer 那么简单了。": (
        "真正可迁移的内容不是术语或固定表达，而是技术之间的联系、方案随约束变化的方式、定位问题的证据链，以及把复杂机制讲清楚的能力。"
    ),
    "技术讨论中呢？答案就更加简单了，Cache Aside 大家都会，我凭什么给你 offer 呢？": (
        "在工程评审中，只复述 Cache Aside 仍不足以证明方案适用于当前业务约束。"
    ),
    "我个人认为，即便公司用不着，你自己也应该尝试一下，毕竟还是那句话，简单的东西大家都会，你凭什么在技术讨论中拿到 offer 呢？": (
        "即使线上当前不需要更复杂的方案，也可以用最小并发实验复现旧值回填，再比较版本号、延迟删除或变更事件的收敛效果。"
    ),
    "我在这节课里面列出了很多优化方案，你还知道别的优化方案吗？如果你出去技术讨论，你准备用什么话术来介绍你的优化方案？在冷热分离中，一般冷数据我们的都是用机械硬盘，而热数据就是用固态硬盘，你知道这是为什么吗？": (
        "除了本节方案，还应尝试提出一个替代方案并用 profile 数据比较。冷热分离为什么常把冷数据放在容量型存储、热数据放在低延迟存储，也应从访问频率、成本与尾延迟解释，而不是只记硬件名称。"
    ),
    "不知不觉已经到了课程的最后一章了。这一章的内容虽然较前几章来说没那么多，但是NoSQL 的内容还是很重要的，尤其是近几年，在技术讨论中出现的频次越来越高。所以为了让你对这部分内容掌握得更加牢固，我列出了一些问题，帮助你编织出自己的知识网络。": (
        "NoSQL 专题内容不多，但需要把访问模型、分片路由、副本确认、查询执行和恢复路径连接起来。下面用一组问题检查这些知识是否已经形成网络。"
    ),
    "不过创新也会遇到重重阻碍，比如组织关系上、团队协作上，都很容易推进不下去，让方案夭折。我们的课程提到的基本都是技术面可能出现的问题及应对之策，但有些职业可能还会考察你的软实力，不免会出现一些非技术类的问题，不过和这门课程方向相左，我也没有详细聊这方面的内容，不过如果你感兴趣的话，可以在评论区分享你的故事和困境，我们一起帮你出谋划策。": (
        "创新也会遇到组织关系和团队协作阻力。技术正确只是前提，还要把风险、迁移步骤、回滚条件和验证结果表达清楚，让相关团队能够共同推进。"
    ),
}

PROMOTIONAL_LINE_TOKENS = (
    "一名热爱开源的 IT 猛男",
    "Beego 的 PMC",
    "手捏好几个大厂 offer",
    "下一个 offer 收割机",
    "极客时间训练营",
    "我的训练营里面写过",
    "训练营的学员",
    "课程终于要完结",
    "虽然我出这门课程",
    "结课问卷",
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
    "15-data-migration": [
        ("MySQL 8.4 · Binary Log", "https://dev.mysql.com/doc/refman/8.4/en/binary-log.html"),
        ("Debezium · MySQL Connector", "https://debezium.io/documentation/reference/stable/connectors/mysql.html"),
    ],
    "16-sharding-id": [
        ("Twitter Archive · Snowflake", "https://github.com/twitter-archive/snowflake"),
    ],
    "17-sharding-pagination": [
        ("MySQL 8.4 · LIMIT Query Optimization", "https://dev.mysql.com/doc/refman/8.4/en/limit-optimization.html"),
    ],
    "18-distributed-transactions": [
        ("MySQL 8.4 · XA Transactions", "https://dev.mysql.com/doc/refman/8.4/en/xa.html"),
    ],
    "19-sharding-secondary-query": [
        ("Vitess · Vindexes", "https://vitess.io/docs/reference/features/vindexes/"),
    ],
    "20-sharding-capacity": [
        ("Vitess · Resharding", "https://vitess.io/docs/user-guides/configuration-advanced/resharding/"),
    ],
    "21-database-architecture": [
        ("MySQL 8.4 · Replication", "https://dev.mysql.com/doc/refman/8.4/en/replication.html"),
        ("MySQL 8.4 · Group Replication", "https://dev.mysql.com/doc/refman/8.4/en/group-replication.html"),
    ],
    "21a-mock-database": [
        ("MySQL 8.4 · Optimization", "https://dev.mysql.com/doc/refman/8.4/en/optimization.html"),
        ("MySQL 8.4 · InnoDB", "https://dev.mysql.com/doc/refman/8.4/en/innodb-storage-engine.html"),
    ],
    "消息队列": [
        ("Apache Kafka · Introduction", "https://kafka.apache.org/documentation/"),
        ("Apache Kafka · Design", "https://kafka.apache.org/41/design/design/"),
    ],
    "数据库": [
        ("MySQL 8.4 Reference Manual", "https://dev.mysql.com/doc/refman/8.4/en/"),
        ("MySQL 8.4 · InnoDB", "https://dev.mysql.com/doc/refman/8.4/en/innodb-storage-engine.html"),
    ],
    "消息队列": [
        ("Apache Kafka · Documentation", "https://kafka.apache.org/documentation/"),
        ("Apache Kafka · Design", "https://kafka.apache.org/25/design/design/"),
    ],
    "31-redis-expiration": [
        ("Redis · EXPIRE and expiration internals", "https://redis.io/docs/latest/commands/expire/"),
        ("Redis · Diagnosing latency issues", "https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/latency/"),
    ],
    "32-cache-eviction": [
        ("Redis · Key eviction", "https://redis.io/docs/latest/develop/reference/eviction/"),
        ("Redis · Memory optimization", "https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/memory-optimization/"),
    ],
    "33-cache-patterns": [
        ("Redis · Client-side caching", "https://redis.io/docs/latest/develop/clients/client-side-caching/"),
        ("Redis · Keyspace notifications", "https://redis.io/docs/latest/develop/pubsub/keyspace-notifications/"),
    ],
    "34-cache-consistency": [
        ("Redis · Client-side caching", "https://redis.io/docs/latest/develop/clients/client-side-caching/"),
        ("Redis · Transactions", "https://redis.io/docs/latest/develop/using-commands/transactions/"),
    ],
    "35-cache-failures": [
        ("Redis · Key eviction", "https://redis.io/docs/latest/develop/reference/eviction/"),
        ("Redis · Redis pipelining", "https://redis.io/docs/latest/develop/using-commands/pipelining/"),
    ],
    "36-redis-single-thread": [
        ("Redis · Diagnosing latency issues", "https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/latency/"),
        ("Redis · Latency monitoring", "https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/latency-monitor/"),
    ],
    "37-redis-distributed-lock": [
        ("Redis · Distributed Locks", "https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/"),
        ("Redis · SET command", "https://redis.io/docs/latest/commands/set/"),
    ],
    "38-cache-architecture": [
        ("Redis · Client-side caching", "https://redis.io/docs/latest/develop/clients/client-side-caching/"),
        ("Redis · High availability with Sentinel", "https://redis.io/docs/latest/operate/oss_and_stack/management/sentinel/"),
    ],
    "38a-mock-cache": [
        ("Redis · Documentation", "https://redis.io/docs/latest/"),
        ("Redis · Key eviction", "https://redis.io/docs/latest/develop/reference/eviction/"),
    ],
    "缓存": [
        ("Redis · Documentation", "https://redis.io/docs/latest/"),
        ("Redis · Key eviction", "https://redis.io/docs/latest/develop/reference/eviction/"),
    ],
    "39-elasticsearch-ha": [
        ("Elastic · Shard allocation, relocation, and recovery", "https://www.elastic.co/docs/deploy-manage/distributed-architecture/shard-allocation-relocation-recovery"),
        ("Elastic · Snapshot and restore", "https://www.elastic.co/docs/deploy-manage/tools/snapshot-and-restore"),
    ],
    "40-elasticsearch-query": [
        ("Elastic · Paginate search results", "https://www.elastic.co/docs/reference/elasticsearch/rest-apis/paginate-search-results"),
        ("Elastic · Query and filter context", "https://www.elastic.co/docs/reference/query-languages/query-dsl/query-filter-context"),
    ],
    "41-mongodb-ha": [
        ("MongoDB · Replica Set Read and Write Semantics", "https://www.mongodb.com/docs/manual/applications/replication/"),
        ("MongoDB · Shards", "https://www.mongodb.com/docs/manual/core/sharded-cluster-shards/"),
        ("MongoDB · Write Concern", "https://www.mongodb.com/docs/manual/reference/write-concern/"),
    ],
    "42-mongodb-performance": [
        ("MongoDB · ESR Guideline", "https://www.mongodb.com/docs/manual/tutorial/equality-sort-range-guideline/"),
        ("MongoDB · Compound Indexes", "https://www.mongodb.com/docs/manual/core/indexes/index-types/index-compound/"),
    ],
    "42a-mock-nosql": [
        ("Elastic · Distributed architecture", "https://www.elastic.co/docs/deploy-manage/distributed-architecture/clusters-nodes-shards"),
        ("MongoDB · Database Manual", "https://www.mongodb.com/docs/manual/"),
    ],
    "NoSQL": [
        ("Elasticsearch · Distributed architecture", "https://www.elastic.co/docs/deploy-manage/distributed-architecture/clusters-nodes-shards"),
        ("MongoDB · Manual", "https://www.mongodb.com/docs/manual/"),
    ],
    "综合": [
        ("Google SRE · Monitoring Distributed Systems", "https://sre.google/sre-book/monitoring-distributed-systems/"),
        ("OpenTelemetry · Traces", "https://opentelemetry.io/docs/concepts/signals/traces/"),
    ],
    "导学": [
        ("Google SRE · The Site Reliability Workbook", "https://sre.google/workbook/table-of-contents/"),
        ("OpenTelemetry · Observability Primer", "https://opentelemetry.io/docs/concepts/observability-primer/"),
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
    "15-data-migration": (
        "全量快照与增量日志必须共享一个可解释的位点或顺序边界，否则无法证明快照期间发生的更新没有遗漏。"
        "CDC 连接器能提供变更流，但双写原子性、业务幂等、字段语义和切流回滚仍由迁移状态机负责。"
    ),
    "16-sharding-id": (
        "Snowflake 是一种把时间、节点和序列组合进整数的设计家族，不是一个自动解决时钟回拨和节点号冲突的协议。"
        "位宽、纪元、节点分配与回拨策略必须按实现说明；趋势递增也不等于全局连续。"
    ),
    "17-sharding-pagination": (
        "MySQL 的 LIMIT 优化仍需要结合 ORDER BY、索引和实际执行计划理解。跨分片游标分页要求一个稳定、唯一的全局排序边界，"
        "通常用 `(sort_key, id)`；只携带可能重复的时间字段会产生重复或遗漏。"
    ),
    "18-distributed-transactions": (
        "MySQL XA 提供两阶段式资源协调能力，但只覆盖参与 XA 的资源管理器。消息、HTTP 第三方和人工流程不因数据库 XA 自动获得原子性；"
        "这类跨边界流程仍要用可恢复状态、幂等和补偿建模。"
    ),
    "19-sharding-secondary-query": (
        "没有分片键的查询无法凭空定位唯一分片。额外映射、全局二级索引、数据冗余和搜索系统都是在写放大、读延迟、一致性窗口与运维成本之间换取路由能力。"
    ),
    "20-sharding-capacity": (
        "容量规划必须同时计算当前数据量、增长率、热点倾斜、单分片安全上限和故障冗余。分片数一旦写入路由规则就会影响后续迁移成本；"
        "虚拟分片只能降低重映射成本，不能消除真实搬迁。"
    ),
    "21-database-architecture": (
        "复制、读写分离、分库分表和缓存解决的是不同瓶颈。副本读可能受复制延迟影响，分片提高横向容量却增加跨分片查询和迁移成本；"
        "任何组合方案都要写清权威写入点、读一致性要求和故障切换边界。"
    ),
    "21a-mock-database": (
        "数据库方案复盘必须从具体慢查询、锁等待、事务边界和容量证据出发。仅罗列 B+ 树、MVCC、分库分表等术语，不能证明问题定位与方案选择成立。"
    ),
    "22-message-queue": (
        "消息队列能解耦生产与消费时间，但不能自动保证业务成功。生产确认、Broker 耐久、消费处理、offset 提交和下游副作用是不同边界；"
        "必须按业务选择至多一次、至少一次或受限范围的精确一次处理。"
    ),
    "23-delayed-messages": (
        "Kafka 的基础抽象是按分区追加的日志，不原生承诺任意时刻触发每一条消息。利用分区、时间轮、延迟主题或外部存储实现延迟调度时，"
        "都要定义精度、扫描成本、重启恢复、重复触发和热点时间段。"
    ),
    "24-message-ordering": (
        "Kafka 的顺序保证首先落在单个 topic partition 内；业务键需要稳定映射到同一分区。扩分区、重试、并发处理和异步回调都会改变观察到的业务顺序，"
        "所以还要用版本号、串行执行或幂等状态机保护。"
    ),
    "25-message-backlog": (
        "积压是生产速率长期高于有效消费速率的结果。增加消费者只有在可用分区和下游容量允许时才有用；若瓶颈是数据库写入或外部接口，"
        "盲目加消费者只会把积压从 Kafka 搬到下游连接池。"
    ),
    "26-message-durability": (
        "`acks=all` 指等待当前 ISR 中的副本确认，并不字面等于所有配置副本都已写入。它需要与 replication factor、min.insync.replicas 和 leader election 策略共同解释；"
        "生产者收到成功后仍要明确可以容忍的多故障组合。"
    ),
    "27-duplicate-consumption": (
        "至少一次处理允许重投。Kafka 的幂等生产者解决的是生产者到特定分区的重复写入问题，事务可以原子提交 Kafka 输出和消费位点；"
        "写数据库、调用 HTTP 等外部副作用仍需要业务幂等键、唯一约束或状态表配合。"
    ),
    "28-design-a-message-queue": (
        "设计消息队列必须同时定义追加日志、分区路由、复制提交、消费位点、保留清理和故障选主。只画生产者—Broker—消费者三块，无法说明消息在崩溃和重试后是否仍可恢复。"
    ),
    "29-kafka-performance": (
        "Kafka 的性能来自批量、顺序追加、页缓存、压缩和分区并行的组合，而不是“零拷贝”一个词。批量会增加等待和内存，分区会增加元数据与重平衡成本，"
        "每个优化都必须用吞吐、端到端延迟和故障恢复时间共同衡量。"
    ),
    "30-kafka-practice": (
        "高性能与高可靠不是两套互不相关的开关。acks、批量、压缩、分区、复制、消费并发和 offset 提交共同决定吞吐、延迟、重复与丢失窗口；"
        "要在同一压测和故障演练中验证。"
    ),
    "30a-mock-message-queue": (
        "消息专题复盘要能沿一条消息从业务事务、生产发送、Broker 复制、消费处理到下游副作用画出完整时间线，并在任意边界注入崩溃；"
        "只背 Kafka 参数不能证明端到端语义。"
    ),
    "31-redis-expiration": (
        "Redis 官方文档把键过期分成访问时的被动过期与后台主动抽样。TTL 到点后键在语义上已不可读，但物理删除、内存分配器复用以及 RSS 回落不是同一瞬间；"
        "过期机制也不是精确定时任务队列，业务动作不能只靠键空间通知触发。"
    ),
    "32-cache-eviction": (
        "达到 maxmemory 后，Redis 会按 maxmemory-policy 决定淘汰或拒绝会增加内存的命令。LRU/LFU 属于近似选择，并且 volatile 系列只在带 TTL 的键中选候选；"
        "因此策略名称不能替代候选集合、对象大小和业务可丢失性的检查。"
    ),
    "33-cache-patterns": (
        "Cache-Aside、Read-Through、Write-Through 与 Write-Behind 首先区别在谁负责读写真相源、何时确认成功。Redis 的客户端缓存和失效通知可以帮助减少远程读取，"
        "但通知链路、断线重连和本地副本过期仍必须纳入一致性边界。"
    ),
    "34-cache-consistency": (
        "数据库提交与缓存删除通常不是一个原子事务。先写库再删缓存可以缩小常见窗口，却不能凭口号获得强一致；延迟双删、版本号、CDC 失效与短 TTL 都是在不同成本下促进最终收敛，"
        "关键数据仍应从权威存储或版本化状态机判断。"
    ),
    "35-cache-failures": (
        "穿透、热点失效与大量键同时失效会把压力以不同形态传给真相源。布隆过滤器、空值、请求合并、TTL 抖动、限流和旧值服务各有误判、新鲜度或可用性代价；"
        "治理目标应写成数据库最大可承受回源并发，而不只是缓存命中率。"
    ),
    "36-redis-single-thread": (
        "Redis 官方把命令执行描述为 mostly single-threaded，同时明确后台 I/O、持久化等工作可能使用其他线程或进程。单条慢命令会阻塞其他客户端，"
        "所以应关注命令复杂度、网络往返、fork、swap、持久化与内存过期造成的尾延迟，而不是把“单线程”直接等同于慢或绝对无并发。"
    ),
    "37-redis-distributed-lock": (
        "单实例锁应使用带唯一令牌和 TTL 的条件写入，并且只允许持有同一令牌的客户端释放。TTL 只是有期限的租约：执行超时或停顿后，旧持有者仍可能继续操作，"
        "需要下游接受 fencing token 或条件版本。异步复制切主也可能破坏单实例互斥，锁的故障模型必须显式说明。"
    ),
    "38-cache-architecture": (
        "多级缓存会增加独立副本和失效路径。Sentinel 或 Cluster 能改善 Redis 节点故障恢复，却不会自动保证本地缓存、数据库和远程缓存的一致性；"
        "设计必须同时给出每层新鲜度、故障半径、回源上限、版本/失效协议和绕过缓存时的数据库保护。"
    ),
    "38a-mock-cache": (
        "缓存专题最终要通过一次全链路故障演练验收：热点键过期、Redis 不可达、本地副本陈旧和数据库变慢同时发生时，回源并发仍应受控，"
        "而权威数据、允许陈旧窗口和恢复顺序都能从指标与版本信息中解释。"
    ),
    "39-elasticsearch-ha": (
        "Elasticsearch 的主分片是索引操作入口，副本既提供冗余也能服务读取；节点故障后合格副本可被提升，随后通过恢复重新建立缺失副本。"
        "副本会同步逻辑删除和错误写入，因此不能代替快照；恢复带宽与并发也要受控，避免重建流量挤压在线搜索和写入。"
    ),
    "40-elasticsearch-query": (
        "官方文档明确不应使用 from/size 做过深分页，因为每个分片需要保留当前页及之前页面的候选。超过结果窗口的顺序遍历应优先用 search_after，"
        "需要固定索引视图时结合 PIT，并使用唯一且稳定的排序边界；过滤条件不需要相关性评分时应放入 filter context。"
    ),
    "41-mongodb-ha": (
        "复制集提供同一数据集的冗余和选举，分片集群把不同数据子集放在多个分片上，而每个分片本身应部署为复制集。write concern、read concern 与 read preference 分别控制确认、可见性和读取位置，"
        "仲裁节点只投票不保存业务数据，不能等价为数据副本，也不能替代独立备份。"
    ),
    "42-mongodb-performance": (
        "MongoDB 当前官方 ESR 指南并非机械定律：等值字段通常在前；若避免内存排序最重要可选 ESR，若范围极具选择性可考虑 ERS。"
        "复合索引前缀、分片定向路由、keysExamined、docsExamined 和阻塞排序必须用 explain 与真实分布共同验证。"
    ),
    "42a-mock-nosql": (
        "Elasticsearch 与 MongoDB 都能处理文档形态数据，但一个围绕倒排检索与分片归并，一个围绕文档主存储、复制集与分片路由。"
        "若同时使用，应明确唯一真相源、版本化同步、一致性窗口、对账和全量重建，而不是让两个系统互相直接改写。"
    ),
    "43-final-test": (
        "综合架构没有脱离目标的标准答案。限流阈值、超时预算、消息积压上限、缓存陈旧窗口、复制确认和恢复优先级，都必须由用户 SLO、下游安全容量、RPO/RTO 与故障演练数据共同决定。"
    ),
    "44-closing": (
        "产品参数会变化，稳定能力是从现象出发画状态与时间线、量化容量、说明失效边界，再用指标和故障注入反证。复习应持续回到目标版本官方资料与可重复实验，而不是把本稿当成永久不变的配置清单。"
    ),
    "00-introduction": (
        "本课程按工程问题组织知识，但任何章节都不替代目标系统的官方文档、运行数据和故障演练。学习结果应以能否独立推导、设计实验、解释证据和说清边界来验收，而不是以阅读页数或背诵术语计数。"
    ),
}


LESSON_SUPPLEMENTS = {
    "43-final-test": r'''
## 综合演练场：从一张空白纸设计大促下单链路

这里不提供“标准架构图”让你照抄，而是给出一组会互相冲突的约束。你的任务是先算清楚，再决定同步、异步、缓存和降级边界。

### 约束一：先把数字钉在桌面上

| 约束 | 数值 | 它会限制什么 |
| --- | ---: | --- |
| 活动页峰值访问 | 100,000 QPS | 网关、静态资源与缓存入口 |
| 真正提交订单 | 12,000 QPS | 库存资格校验与消息入口 |
| 订单库安全写入 | 8,000 TPS | 同步写入或消费速率上限 |
| 支付接口 P99 | 220 ms | 同步超时预算与未知结果窗口 |
| 用户下单响应目标 | P99 ≤ 500 ms | 同步关键路径总预算 |
| 允许库存展示陈旧 | 3 s | 缓存 TTL 与失效传播窗口 |
| 订单事实 RPO | 0 | 本地事务、日志确认与备份策略 |
| 故障后核心下单恢复 | 10 min | RTO、演练和恢复优先级 |

第一步不是选 Redis、Kafka 或 Elasticsearch，而是检查约束是否自洽：入口允许 12,000 个下单请求进入，但订单库只能稳定写 8,000 条/秒。如果峰值持续 10 分钟，差速是 `12,000 - 8,000 = 4,000 条/秒`，累计积压就是 `4,000 × 600 = 2,400,000 条`。若活动结束后消费者能提升到 10,000 条/秒，而新请求仍有 2,000 条/秒，则净清理速度为 8,000 条/秒，理论上还需 300 秒才能清空。

这组数字揭示两个事实：消息队列只能把压力改成积压，不会扩大数据库容量；系统必须同时规定最大积压、活动后的追平能力，以及积压过大时减少哪些非核心工作。

### 约束二：沿一次请求分配 500 ms 预算

假设用户请求经过网关、资格服务、库存令牌和订单受理四段：

| 阶段 | 预算 | 超时或拒绝后的承诺 |
| --- | ---: | --- |
| 网关认证与限流 | 30 ms | 明确拒绝，不进入下游 |
| 活动资格读取 | 80 ms | 可读 3 秒内旧缓存；无缓存则降级 |
| 库存令牌 | 120 ms | 返回售罄或稍后重试，不绕过令牌直写数据库 |
| 订单受理事务 | 170 ms | 保存订单事实与 Outbox 后返回“已受理” |
| 网络与应用余量 | 100 ms | 吸收抖动，不能被前面各段重复花掉 |

预算总和正好是 500 ms，但这并不意味着每一段都把本段预算耗尽后再重试。若资格服务在 80 ms 末尾重试一次 80 ms，下游已经无预算可用。正确做法是传播同一个截止时间，让每一跳根据剩余时间决定是否还有资格开始下一次尝试。

### 约束三：明确每份状态的唯一所有者

| 状态 | 权威位置 | 可失效副本或派生物 | 收敛方式 |
| --- | --- | --- | --- |
| 订单状态 | 订单数据库 | 用户查询缓存、搜索索引 | Outbox 事件、版本号、对账 |
| 库存事实 | 库存数据库/令牌状态机 | 商品页展示缓存 | 条件更新、事件失效、周期校准 |
| 支付结果 | 支付单状态机 | 前端展示、通知记录 | 幂等支付单号、主动查询、回调去重 |
| 搜索文档 | 不作为订单真相 | Elasticsearch 索引 | 版本化事件、重放、全量重建 |

如果一份状态找不到唯一所有者，就无法判断冲突时相信谁。缓存与搜索都可以比权威存储更快，但它们必须允许删除、重建和暂时落后；否则派生副本会反过来绑架核心事务。

## 连续注入五种故障

不要分别背五套方案。把它们按时间压到同一次活动中，观察保护是否会互相抵消。

### 故障 A：缓存集群完全不可用

活动页仍有 100,000 QPS，而数据库只能承受 3,000 QPS 的读回源。若所有请求直接穿透，数据库会在核心订单写入到来之前被读请求压垮。恢复动作应按顺序发生：先用网关限制回源并返回静态快照或旧值，再让一个受控回填通道恢复热点，最后逐步放量。验收指标不是“缓存恢复了”，而是故障期间数据库读 QPS 从未超过安全水位，订单写入 P99 仍在预算内。

### 故障 B：支付请求超时，但调用方不知道是否扣款

支付调用在 300 ms 处超时，可能是请求没到，也可能是对方已扣款但响应丢失。此时直接生成新支付单再次扣款会制造重复副作用。系统应使用同一业务支付单号查询或重试，由对方幂等约束收敛；本地状态保留 `PROCESSING/UNKNOWN`，由查询任务和回调共同推进，不能把网络超时等同于业务失败。

### 故障 C：消费者处理成功后、提交位置前崩溃

消息会再次到达。订单消费者应在同一本地事务中写业务结果和事件幂等键，第二次处理读取既有结果。若去重只写 Redis，Redis 标记与数据库事务之间仍有崩溃空隙。验证方法是把进程分别杀在事务前、提交后和 offset 提交前，最终都只能产生一次订单状态转换。

### 故障 D：数据库延迟从 20 ms 升到 400 ms

连接池中的慢请求会让排队时间继续放大。熔断器看到的失败率只是结果，真正保护动作还包括缩短入口许可、隔离非核心消费者、暂停搜索派生和通知、限制恢复重试。此时扩消息消费者会更糟，因为它们争抢同一个已饱和数据库。

### 故障 E：搜索索引落后 15 分钟

若订单详情依赖搜索结果，用户会看到“订单不存在”；若搜索只服务模糊检索，详情页仍可回权威订单库。系统应展示索引延迟并暂停依赖新鲜索引的功能，对落后版本重放事件或全量重建。恢复完成必须通过版本对账证明，而不是只看集群状态变绿。

## 你的结课交付物

完成本节不是读到页面底部，而是独立提交以下四份材料：

1. 一张同步关键路径图：每条边标注截止时间、重试条件和幂等键。
2. 一张状态所有权表：每份事实、缓存、消息位置和搜索文档都写明所有者与收敛方式。
3. 一张容量表：给出峰值、下游安全水位、积压增长速度和清空时间。
4. 一张故障矩阵：覆盖缓存全挂、数据库变慢、消息重复、支付未知和索引落后，写清用户体验、自动动作、数据风险、恢复步骤和责任人。

### 自评分标准（100 分）

| 项目 | 分值 | 满分条件 |
| --- | ---: | --- |
| 约束与容量 | 20 | 有明确 SLO、RPO/RTO、峰值和安全水位，并能手算积压 |
| 状态与一致性 | 25 | 权威状态唯一，异步边界、幂等键和对账闭环清楚 |
| 故障保护 | 25 | 超时、隔离、限流和降级不会把压力转移到同一瓶颈 |
| 恢复与证据 | 20 | 每种故障都有指标、日志、演练步骤和可验证终态 |
| 取舍表达 | 10 | 能说明至少两个备选方案及其代价，而非堆产品名 |

少于 80 分时，不必回去从第一页重读。找到失分最多的一行，回到对应专题，用同一组业务数字重新推演；只有推演结果能写进这四份材料，知识才真正连接起来。
''',
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
        line = re.sub(r"[\ue000-\uf8ff]", "", line)
        line = re.sub(r"^作者回复\s*:\s*", "讲解补充：", line)
        line = re.sub(r"^作者回复\s*", "讲解补充：", line)
        line = re.sub(r"^###\s+(.+)$", lambda m: "### " + HEADING_RENAMES.get(m.group(1), m.group(1)), line)
        line = re.sub(r"^##\s+(.+)$", lambda m: "### " + HEADING_RENAMES.get(m.group(1), m.group(1)), line)
        for old, new in PHRASE_REWRITES:
            line = line.replace(old, new)
        line = EDITORIAL_REWRITES.get(line, line)
        if any(token in line for token in PROMOTIONAL_LINE_TOKENS):
            continue
        line = line.replace("大明", "讲解者")
        line = line.replace("《后端工程师的高阶面经》", "本套后端工程学习资料")
        line = re.sub(r"^你好，我是(?:邓明|讲解者)[，,。]?\s*", "", line)
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
    supplement = LESSON_SUPPLEMENTS.get(spec["id"], "")

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

{supplement}

## 按讲解顺序重建知识链：完整来源讲解

下面按来源资料的教学顺序重新编排完整内容。转换页码、来源图片、推广信息、水印和个人宣传已经删除；原本围绕求职问答的角色与措辞改写为工程学习、方案评审和故障复盘语境。机制、算法、例子、反例、事故线索、评论补充和限制条件仍然保留。这里的作用是补齐知识覆盖，不取代前面的独立推演。

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
