#!/usr/bin/env python3
"""Convert the 50 course PDFs into image-backed Markdown lessons.

The converter deliberately keeps the extracted PDF text separate from editorial
context.  Repeated piracy watermarks are the only text removed from the source.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import statistics
from dataclasses import dataclass
from pathlib import Path

import pdfplumber
from PIL import Image
from pypdf import PdfReader


COURSE_PREFIX = "邓明 · 后端工程师的高阶面经"
WATERMARK_RE = re.compile(r"^(防断更\s*[：:]\s*)?97kt\.com$|^防断更\s*[：:].*$", re.I)


LESSONS = {
    1: ("service-discovery", "服务治理", "服务实例、注册中心、心跳、CAP", "先把注册中心理解成一份会变化的服务地址簿：服务端登记地址，客户端订阅地址，心跳负责判断地址是否还可用。AP/CP 的取舍发生在网络分区时，不是日常状态下的二选一。"),
    2: ("load-balancing", "服务治理", "负载均衡、轮询、权重、会话保持", "负载均衡不只是把流量平均分配。请求是否有状态、客户端是否缓存节点、失败结果是否影响权重，都会改变下一次请求该去哪里。"),
    3: ("circuit-breaker", "服务治理", "熔断器、失败率、半开状态、抖动", "熔断器可以看成保护下游的自动开关。关闭时正常放行，打开时快速失败，半开时用少量探测请求判断能否恢复；难点在于阈值和恢复节奏。"),
    4: ("degradation", "服务治理", "降级、核心链路、兜底、容量", "降级的本质是资源不足或依赖异常时主动舍弃次要能力，换取核心链路可用。学习时要区分降级、熔断和限流：它们触发原因与保护对象不同。"),
    5: ("rate-limiting", "服务治理", "限流、令牌桶、漏桶、阈值", "限流算法只解决“怎样拦”，阈值解决“拦到什么程度”。阈值应来自容量测试、历史流量、响应时间目标和安全余量，而不是拍脑袋。"),
    6: ("isolation", "服务治理", "隔离、线程池、连接池、VIP", "隔离是在共享系统里划出故障边界。线程池、连接池、实例、机房和租户都能成为隔离单元，代价是资源利用率与调度复杂度。"),
    7: ("timeout-control", "服务治理", "超时、调用链、预算、重试", "一次请求经过多个服务时，总超时不是每一跳超时的简单复制，而是一份要沿调用链分配的时间预算。重试也会消耗这份预算。"),
    8: ("third-party-calls", "服务治理", "第三方依赖、超时、重试、降级", "第三方接口不受你的团队控制，因此设计目标不是让它永不失败，而是让它失败时不拖垮主流程，并保留补偿、对账和人工处理入口。"),
    9: ("service-governance", "服务治理", "高可用、故障域、治理组合", "单个治理手段只处理一种风险。完整方案通常按故障发生前、发生中、发生后组合容量评估、隔离、限流、熔断、降级、超时与观测。"),
    10: ("mysql-index", "数据库", "B+ 树、B 树、页、范围查询", "数据库索引是磁盘页上的有序结构。比较 B 树与 B+ 树时，要同时考虑树高、一次 I/O 能读多少键、叶子节点链表以及范围扫描。"),
    11: ("sql-optimization", "数据库", "执行计划、索引、扫描行数、回表", "SQL 优化先定位瓶颈，再改写语句或索引。执行计划是数据库对访问路径的估算，不等于真实执行结果；需要结合慢日志与实际统计判断。"),
    12: ("database-locks", "数据库", "行锁、表锁、间隙锁、索引", "数据库锁住的往往是索引记录或索引区间，而不是抽象的“这一行”。是否命中索引、隔离级别和执行计划都会改变锁范围。"),
    13: ("mvcc", "数据库", "MVCC、版本链、Read View、隔离级别", "MVCC 用多版本让读写尽量不互相阻塞。理解它要抓住三件事：旧版本存在哪里、一次读取能看见哪些版本、不同隔离级别何时创建可见性快照。"),
    14: ("database-transactions", "数据库", "事务、WAL、redo log、持久性", "事务提交成功只代表数据库在其承诺边界内完成了持久化。操作系统缓存、磁盘刷写策略、主从复制和备份恢复仍是不同层次的问题。"),
    15: ("data-migration", "数据库", "数据迁移、双写、CDC、校验", "不停机迁移通常经历全量复制、增量追平、双写或变更捕获、校验和切流。真正困难的是切换期间新旧数据如何保持一致以及失败后怎样回滚。"),
    16: ("sharding-id", "数据库", "全局 ID、趋势递增、唯一性、时钟回拨", "分库分表后，自增主键无法天然跨库唯一。全局 ID 需要在唯一性、趋势递增、可用性、性能、信息泄露和时钟依赖之间权衡。"),
    17: ("sharding-pagination", "数据库", "分库分表、分页、归并、游标", "跨分片分页要从多个分片各取候选结果再全局归并。offset 越大，丢弃的数据越多；游标或按上次排序键继续查询通常更稳定。"),
    18: ("distributed-transactions", "数据库", "分布式事务、2PC、TCC、Saga", "ACID 是单个事务边界内的目标；跨服务后需要协调多个本地事务。2PC、TCC、Saga 和事务消息分别选择了不同的一致性、侵入性与恢复方式。"),
    19: ("sharding-secondary-query", "数据库", "分片键、二级索引、数据冗余、广播", "按买家分片后，卖家查询缺少路由信息。常见解法是额外索引表、数据冗余、搜索系统或广播查询，它们把查询成本转移到写入、存储或一致性上。"),
    20: ("sharding-capacity", "数据库", "容量评估、分片数、增长率、扩容", "分片数量应从未来数据量、单表容量、读写 QPS、热点和扩容成本反推。预留余量很重要，但过度分片也会增加运维与查询复杂度。"),
    21: ("database-architecture", "数据库", "高可用、高性能、主从、分片", "数据库架构题要先澄清目标与约束，再分别处理读、写、容量、故障恢复和一致性。不要一上来罗列中间件。"),
    22: ("message-queue", "消息队列", "异步、解耦、削峰、最终一致性", "消息队列把发送方和处理方在时间上分开。它能带来异步、解耦和削峰，同时也引入延迟、重复、丢失、顺序与积压问题。"),
    23: ("delayed-messages", "消息队列", "延迟消息、时间轮、定时任务、Kafka", "Kafka 原生模型围绕按顺序追加和消费设计，不等于天然支持任意延迟投递。实现延迟消息通常需要额外主题、时间轮或调度服务。"),
    24: ("message-ordering", "消息队列", "有序消息、分区、消息键、并发", "全局有序成本很高，业务通常只要求同一实体的消息有序。把相同业务键路由到同一分区，再约束分区内消费并发即可获得局部顺序。"),
    25: ("message-backlog", "消息队列", "消息积压、消费能力、分区、扩容", "积压意味着生产速率持续高于消费速率。先判断是突发流量还是消费者故障，再从并发度、分区数、单条处理耗时和下游容量入手。"),
    26: ("message-durability", "消息队列", "消息丢失、确认、复制、刷盘", "“发送成功”在生产者、Broker 和消费者三个阶段有不同含义。要逐段检查确认机制、复制、持久化和消费位点。"),
    27: ("duplicate-consumption", "消息队列", "重复消费、幂等、去重、事务", "多数消息系统更容易提供至少一次投递，因此业务必须能承受重复。幂等键、唯一约束、状态机和去重表是常见手段。"),
    28: ("design-a-message-queue", "消息队列", "架构设计、Broker、存储、消费组", "设计消息队列时先定义投递语义和场景，再拆生产者、Broker、存储、复制、消费组、元数据与运维体系。"),
    29: ("kafka-performance", "消息队列", "顺序写、批处理、零拷贝、页缓存", "Kafka 的性能来自一组协同设计：追加写、批量、压缩、页缓存、分区并行和减少数据复制，而不是某一个魔法优化。"),
    30: ("kafka-practice", "消息队列", "Kafka、吞吐、延迟、可靠性", "实践中的 Kafka 调优要在吞吐、延迟、可靠性和资源之间权衡。生产端、Broker、主题分区与消费端必须一起观察。"),
    31: ("redis-expiration", "缓存", "过期键、惰性删除、定期删除、CPU", "Redis 不在到期瞬间逐个删除所有键，是为了避免维护精确计时器和集中删除占满 CPU。惰性删除与定期抽样共同回收。"),
    32: ("cache-eviction", "缓存", "淘汰策略、LRU、LFU、命中率", "内存不足时淘汰谁，本质是在预测未来访问。LRU 看最近，LFU 看频率；业务访问分布与缓存大小决定哪种策略更合适。"),
    33: ("cache-patterns", "缓存", "Cache Aside、Read Through、Write Through", "缓存模式定义读写由谁负责以及先写哪一边。模式能规范流程，却不能自动消除数据库与缓存两个副本之间的一致性窗口。"),
    34: ("cache-consistency", "缓存", "一致性、延迟双删、消息、版本号", "缓存一致性通常追求业务可接受的最终一致，而非跨数据库和缓存的强事务。关键是识别并发读写窗口，并设计失效、重试和校验。"),
    35: ("cache-failures", "缓存", "穿透、击穿、雪崩、热点", "穿透是查询不存在数据，击穿是热点键失效，雪崩是大量键或缓存服务同时失效。三者现象相似，但治理手段不同。"),
    36: ("redis-single-thread", "缓存", "事件循环、I/O 多路复用、单线程", "讨论 Redis 单线程要先限定范围：核心命令执行路径长期以单线程为主，但网络 I/O、持久化和后台任务可能使用其他线程或进程，且版本实现会变化。"),
    37: ("redis-distributed-lock", "缓存", "分布式锁、租约、续约、 fencing token", "分布式锁不只是 SETNX。还要处理唯一持有者、过期、续约、误删、进程暂停和网络分区；关键资源可用 fencing token 防止旧持有者继续写。"),
    38: ("cache-architecture", "缓存", "缓存架构、热点、高可用、一致性", "缓存综合题要从是否值得缓存开始，再讨论键设计、容量、过期、淘汰、一致性、热点、故障和观测。"),
    39: ("elasticsearch-ha", "NoSQL 与搜索", "Elasticsearch、分片、副本、主节点", "Elasticsearch 把索引拆成主分片并为其配置副本。高可用依赖节点角色、分片分配、故障检测与集群状态管理。"),
    40: ("elasticsearch-query", "NoSQL 与搜索", "倒排索引、过滤、分页、聚合", "查询性能取决于映射、分片规模、查询写法和返回结果。全文相关性查询、精确过滤、聚合与深分页的成本模型不同。"),
    41: ("mongodb-ha", "NoSQL 与搜索", "MongoDB、副本集、选举、写关注", "MongoDB 副本集通过主节点写入、从节点复制和选举实现故障切换。写关注和读关注决定客户端愿意为一致性与持久性等待多少。"),
    42: ("mongodb-performance", "NoSQL 与搜索", "MongoDB、索引、文档模型、查询计划", "MongoDB 性能优化同样从数据模型、索引和执行计划入手。文档嵌入与引用的选择会直接影响查询次数、文档大小和更新成本。"),
}


@dataclass
class CatalogItem:
    order: float
    slug: str
    chapter: str
    title: str
    filename: str
    context_terms: str
    context: str


def clean_title(filename: str) -> str:
    title = re.sub(r"【优质IT课程.*?】", "", Path(filename).stem)
    title = title.replace("｜", "｜").strip()
    return title


def classify(path: Path) -> CatalogItem:
    title = clean_title(path.name)
    match = re.match(r"^(\d{2})｜", title)
    if match:
        num = int(match.group(1))
        slug, chapter, terms, context = LESSONS[num]
        return CatalogItem(float(num), f"{num:02d}-{slug}", chapter, title, path.name, terms, context)
    if title.startswith("开篇词"):
        return CatalogItem(0, "00-introduction", "导学", title, path.name, "面试准备、项目经验、表达结构", "这门课的目标不是背标准答案，而是把项目经验组织成有背景、有取舍、有结果的技术叙事。先建立学习方法，再进入具体主题。")
    if "微服务架构" in title:
        return CatalogItem(9.5, "09a-mock-service-governance", "服务治理", title, path.name, "面试主线、追问、项目证据", "模拟面试用于把前面各知识点串成回答主线。阅读时先自己口述，再对照原文检查是否说明了场景、方案、取舍和效果。")
    if "数据库面试" in title:
        return CatalogItem(21.5, "21a-mock-database", "数据库", title, path.name, "索引、事务、分库分表、架构", "这份模拟面试把数据库各主题连成一条追问路径。重点不是记顺序，而是练习从业务约束推导技术选择。")
    if "消息队列面试" in title:
        return CatalogItem(30.5, "30a-mock-message-queue", "消息队列", title, path.name, "投递语义、积压、顺序、可靠性", "回答消息队列问题时，要始终区分生产、Broker、消费三个阶段，并明确自己承诺的是最多一次、至少一次还是业务幂等后的效果。")
    if "缓存面试" in title:
        return CatalogItem(38.5, "38a-mock-cache", "缓存", title, path.name, "缓存模式、一致性、热点、故障", "缓存题容易变成名词堆砌。这份模拟面试适合训练从访问模式和一致性要求出发，逐步解释为何需要某种缓存方案。")
    if "NoSQL" in title:
        return CatalogItem(42.5, "42a-mock-nosql", "NoSQL 与搜索", title, path.name, "数据模型、分片、副本、查询", "NoSQL 不是单一技术类别。回答时先说明数据模型与查询需求，再讨论分片、副本、一致性和性能，避免只背产品特性。")
    if title.startswith("结课测试"):
        return CatalogItem(43, "43-final-test", "复习与测试", title, path.name, "综合测试、查漏补缺", "先在不翻资料的情况下完成测试，再回到对应课程定位薄弱环节。测试的价值是暴露知识断点，不是只看分数。")
    if title.startswith("结束语"):
        return CatalogItem(44, "44-closing", "复习与测试", title, path.name, "复盘、实践、持续学习", "完成课程后，把每个主题压缩成自己的项目案例和一页复习卡；能解释取舍、边界与失败模式，才算真正掌握。")
    raise ValueError(f"Unclassified PDF: {path.name}")


def is_watermark(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    return bool(WATERMARK_RE.match(compact)) or "防断更：97kt.com" in compact


def join_lines(lines: list[dict]) -> list[tuple[str, str]]:
    """Return (kind, text) blocks while preserving all non-watermark text."""
    blocks: list[tuple[str, str]] = []
    paragraph: list[str] = []
    previous_bottom: float | None = None

    def flush() -> None:
        nonlocal paragraph
        if paragraph:
            text = paragraph[0]
            for continuation in paragraph[1:]:
                separator = " " if text[-1:].isascii() and text[-1:].isalnum() and continuation[:1].isascii() and continuation[:1].isalnum() else ""
                text += separator + continuation
            text = re.sub(r"([A-Za-z0-9])\s+([A-Za-z0-9])", r"\1 \2", text)
            blocks.append(("paragraph", text.strip()))
            paragraph = []

    for line in lines:
        text = line["text"].strip()
        if not text or is_watermark(text):
            continue
        chars = line.get("chars") or []
        size = statistics.median([float(char.get("size", 0)) for char in chars]) if chars else 0
        gap = None if previous_bottom is None else float(line["top"]) - previous_bottom
        previous_bottom = float(line["bottom"])

        if size >= 14.0:
            flush()
            blocks.append(("heading", text))
            continue

        list_match = re.match(r"^((?:\d+|[①②③④⑤⑥⑦⑧⑨⑩])[.、]|[-•])\s*", text)
        if list_match:
            flush()
            normalized = re.sub(r"^(\d+)[、.]\s*", r"\1. ", text)
            normalized = re.sub(r"^[•]\s*", "- ", normalized)
            blocks.append(("list", normalized))
            continue

        if gap is not None and gap < 18 and not paragraph and blocks and blocks[-1][0] == "list":
            kind, previous = blocks[-1]
            separator = " " if previous[-1:].isascii() and previous[-1:].isalnum() and text[:1].isascii() and text[:1].isalnum() else ""
            blocks[-1] = (kind, previous + separator + text)
            continue

        if gap is not None and gap >= 18:
            flush()
        paragraph.append(text)

    flush()
    return blocks


def extract_images(
    reader: PdfReader,
    pdf_page: pdfplumber.page.Page,
    page_index: int,
    asset_dir: Path,
    slug: str,
) -> list[str]:
    saved: list[str] = []
    seen: set[str] = set()
    had_decode_error = False
    page_images = reader.pages[page_index].images
    for image_index in range(1, len(page_images) + 1):
        try:
            image_file = page_images[image_index - 1]
        except Exception as error:
            had_decode_error = True
            print(
                f"  warning: skipped undecodable image on page {page_index + 1}: "
                f"{type(error).__name__}",
                flush=True,
            )
            continue
        data = image_file.data
        digest = hashlib.sha1(data).hexdigest()[:10]
        if digest in seen:
            continue
        seen.add(digest)
        try:
            with Image.open(io.BytesIO(data)) as image:
                width, height = image.size
                fmt = (image.format or "PNG").lower()
        except Exception:
            continue
        # Logos, UI icons, and comment avatars are deliberately ignored. Course
        # illustrations, diagrams, code shots, and mind maps easily exceed this.
        if width < 420 or height < 120:
            continue
        suffix = "jpg" if fmt in {"jpeg", "jpg"} else "png"
        name = f"{slug}-p{page_index + 1:02d}-{image_index:02d}-{digest}.{suffix}"
        destination = asset_dir / name
        destination.write_bytes(data)
        saved.append(name)

    # A small number of PDFs contain a visually valid image whose compressed
    # stream exceeds pypdf's safe decoder limit. Recover the exact image region
    # from the rendered PDF page instead of dropping it or rasterizing the page.
    if had_decode_error and not saved:
        for image_index, image_meta in enumerate(pdf_page.images, start=1):
            if float(image_meta.get("width", 0)) < 420 or float(image_meta.get("height", 0)) < 120:
                continue
            bbox = (
                float(image_meta["x0"]),
                float(image_meta["top"]),
                float(image_meta["x1"]),
                float(image_meta["bottom"]),
            )
            rendered = pdf_page.crop(bbox).to_image(resolution=180, antialias=True).original
            name = f"{slug}-p{page_index + 1:02d}-{image_index:02d}-rendered.png"
            rendered.save(asset_dir / name, format="PNG", optimize=True)
            saved.append(name)
    return saved


def convert(pdf_path: Path, item: CatalogItem, output_dir: Path, asset_dir: Path) -> dict:
    reader = PdfReader(str(pdf_path))
    escaped_title = item.title.replace('"', '\\"')
    escaped_filename = item.filename.replace('"', '\\"')
    guiding_question = re.sub(r"^\d{2}｜", "", item.title)
    markdown: list[str] = [
        "---",
        f'id: "{item.slug}"',
        f"order: {item.order:g}",
        f'chapter: "{item.chapter}"',
        f'title: "{escaped_title}"',
        f'source_file: "{escaped_filename}"',
        f"source_pages: {len(reader.pages)}",
        'content_status: "complete"',
        "---",
        "",
        f"# {item.title}",
        "",
        f"> 课程：{COURSE_PREFIX}  \n> 来源：本地 PDF 转换，共 {len(reader.pages)} 页。页面标记可用于回查原 PDF。",
        "",
        "## 学习前补齐（编者补充）",
        "",
        "> 本节为帮助理解而补充，不属于原 PDF 内容。涉及具体产品行为时，应以你实际使用版本的官方文档为准。",
        "",
        f"**先认识这些词：** {item.context_terms}。",
        "",
        item.context,
        "",
        f"**带着这个问题阅读：** {guiding_question}",
        "",
        "---",
        "",
        "## PDF 原文",
        "",
    ]
    total_source_chars = 0
    total_kept_chars = 0
    total_converted_chars = 0
    total_converted_chars_normalized = 0
    image_count = 0
    in_discussion = False

    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_index, page in enumerate(pdf.pages):
            lines = page.extract_text_lines(return_chars=True, use_text_flow=False)
            total_source_chars += sum(len(line["text"].strip()) for line in lines if line["text"].strip())
            kept = [line for line in lines if line["text"].strip() and not is_watermark(line["text"].strip())]
            total_kept_chars += sum(len(line["text"].strip()) for line in kept)
            blocks = join_lines(lines)
            images = extract_images(reader, page, page_index, asset_dir, item.slug)
            image_count += len(images)

            markdown.extend([f"<!-- source-page: {page_index + 1} -->", ""])
            for image_name in images:
                markdown.extend([f"![{item.title} - 第 {page_index + 1} 页课程图](./assets/{image_name})", ""])

            for kind, text in blocks:
                if text == item.title or text == COURSE_PREFIX:
                    continue
                total_converted_chars += len(text)
                total_converted_chars_normalized += len(re.sub(r"\s+", "", text))
                if "全部留言" in text and not in_discussion:
                    markdown.extend(["## 课后讨论（PDF 原文）", ""])
                    in_discussion = True
                if kind == "heading":
                    level = "###" if not in_discussion else "####"
                    markdown.extend([f"{level} {text}", ""])
                elif kind == "list":
                    markdown.append(text)
                else:
                    markdown.extend([text, ""])
            markdown.append("")

    md_path = output_dir / f"{item.slug}.md"
    md_path.write_text("\n".join(markdown).rstrip() + "\n", encoding="utf-8")
    return {
        "id": item.slug,
        "order": item.order,
        "chapter": item.chapter,
        "title": item.title,
        "markdown": md_path.name,
        "source_file": item.filename,
        "source_pages": len(reader.pages),
        "source_chars": total_source_chars,
        "kept_chars": total_kept_chars,
        "converted_chars": total_converted_chars,
        "converted_chars_normalized": total_converted_chars_normalized,
        "image_count": image_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=Path("content"))
    args = parser.parse_args()

    output_dir = args.output.resolve()
    asset_dir = output_dir / "assets"
    output_dir.mkdir(parents=True, exist_ok=True)
    asset_dir.mkdir(parents=True, exist_ok=True)

    pdfs = [path for path in args.source.glob("*.pdf") if path.is_file()]
    items = sorted(((classify(path), path) for path in pdfs), key=lambda pair: pair[0].order)
    if len(items) != 50:
        raise SystemExit(f"Expected 50 PDFs, found {len(items)}")

    catalog = []
    for index, (item, path) in enumerate(items, start=1):
        print(f"[{index:02d}/50] {item.title}", flush=True)
        catalog.append(convert(path, item, output_dir, asset_dir))

    (output_dir / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Converted {len(catalog)} PDFs into {output_dir}")


if __name__ == "__main__":
    main()
