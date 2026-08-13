#!/usr/bin/env python3
"""Deterministic service-discovery and client-failover walkthrough."""

from dataclasses import dataclass


@dataclass
class Instance:
    name: str
    address: str
    alive: bool = True


instances = {
    "库存-上海": Instance("库存-上海", "10.0.0.11:8080"),
    "库存-杭州": Instance("库存-杭州", "10.0.0.12:8080"),
    "库存-宁波": Instance("库存-宁波", "10.0.0.13:8080"),
}

# 订单服务从注册中心订阅后得到的本地节点表。
local_view = list(instances)
quarantine: set[str] = set()


def call_inventory(request_id: str) -> None:
    """Try local candidates in order; quarantine a node after a failed call."""
    print(f"\n请求 {request_id}，本地节点表={local_view}，隔离区={sorted(quarantine)}")
    for name in local_view:
        if name in quarantine:
            continue
        node = instances[name]
        print(f"尝试 {name}({node.address})", end=" -> ")
        if not node.alive:
            print("连接失败，放入隔离区")
            quarantine.add(name)
            continue
        print("调用成功")
        return
    raise RuntimeError("没有可用库存节点")


call_inventory("req-001")

# 上海节点突然断电；注册中心的通知还没有到达订单服务。
instances["库存-上海"].alive = False
print("\n事件：库存-上海突然断电，但订单服务仍握着旧节点表。")
call_inventory("req-002")

# 后台探测发现上海节点恢复，只能在确认可达后重新纳入。
instances["库存-上海"].alive = True
quarantine.remove("库存-上海")
print("\n事件：后台探测成功，库存-上海移出隔离区。")
call_inventory("req-003")
