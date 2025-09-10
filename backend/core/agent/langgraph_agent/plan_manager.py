from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
import json


@dataclass
class Node:
    id: str
    type: str
    title: str
    thoughts: str
    sources: List[str] = field(default_factory=list)    # 执行依赖（数据流）
    parent: Optional[str] = None                       # 规划父节点（分层）
    children: List[str] = field(default_factory=list)  # 规划子节点（分层）
    dynamic: bool = False                              # 是否占位/可拆解
    status: str = "pending"                            # pending|done|failed
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，用于序列化"""
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "thoughts": self.thoughts,
            "sources": list(self.sources),
            "parent": self.parent,
            "children": list(self.children),
            "dynamic": self.dynamic,
            "status": self.status
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Node':
        """从字典格式创建Node实例"""
        return cls(
            id=data["id"],
            type=data["type"],
            title=data["title"],
            thoughts=data["thoughts"],
            sources=list(data.get("sources", [])),
            parent=data.get("parent"),
            children=list(data.get("children", [])),
            dynamic=data.get("dynamic", False),
            status=data.get("status", "pending")
        )


class PlanManager:
    def __init__(self):
        self.title: str = ""
        self.thought: str = ""
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, Set[str]] = {}           # 依赖边 src->dst
        self.observations: Dict[str, Any] = {}
        # 记录"谁原本依赖过这个动态占位节点"，用于后续重定向
        self.dynamic_dependents: Dict[str, Set[str]] = {}  # dynamic_id -> {downstream_id}

    # ---------------- 基础增删改 ----------------
    def add_node(self, spec: Dict[str, Any]) -> None:
        """根据 JSON 规范添加/合并一个节点。
        允许局部更新字段，并维护分层父子关系与依赖边。
        """
        nid = spec["id"]
        node = self.nodes.get(nid)
        if node is None:
            node = Node(
                id=nid,
                type=spec.get("type", "task"),
                title=spec.get("title", nid),
                thoughts=spec.get("thoughts", ""),
                sources=list(spec.get("sources", [])),
                parent=spec.get("parent"),
                dynamic=bool(spec.get("dynamic", False)),
            )
            self.nodes[nid] = node
            self.edges.setdefault(nid, set())
        else:
            # 合并/更新
            node.type = spec.get("type", node.type)
            node.title = spec.get("title", node.title)
            node.thoughts = spec.get("thoughts", node.thoughts)
            for s in spec.get("sources", []):
                if s not in node.sources:
                    node.sources.append(s)
            if "dynamic" in spec:
                node.dynamic = bool(spec["dynamic"])
            if "parent" in spec and spec["parent"] is not None:
                node.parent = spec["parent"]

        # 分层父子
        if node.parent:
            self.nodes.setdefault(
                node.parent,
                Node(
                    id=node.parent,
                    type="placeholder",
                    title=f"(placeholder {node.parent})",
                    thoughts="",
                    dynamic=True,
                ),
            )
            if nid not in self.nodes[node.parent].children:
                self.nodes[node.parent].children.append(nid)

        # 依赖边
        for s in node.sources:
            self._ensure_node_exists(s)
            self.edges.setdefault(s, set()).add(nid)
            # 记录动态依赖
            if self.nodes[s].dynamic:
                self.dynamic_dependents.setdefault(s, set()).add(nid)

    def add_nodes(self, specs: List[Dict[str, Any]]) -> None:
        for spec in specs:
            self.add_node(spec)

    def add_edge(self, src: str, dst: str) -> None:
        self._ensure_node_exists(src)
        self._ensure_node_exists(dst)
        if src not in self.nodes[dst].sources:
            self.nodes[dst].sources.append(src)
        self.edges.setdefault(src, set()).add(dst)
        if self.nodes[src].dynamic:
            self.dynamic_dependents.setdefault(src, set()).add(dst)

    def _ensure_node_exists(self, nid: str) -> None:
        if nid not in self.nodes:
            self.nodes[nid] = Node(
                id=nid,
                type="placeholder",
                title=f"(placeholder {nid})",
                thoughts="",
                dynamic=False,
            )
            self.edges.setdefault(nid, set())

    def _incoming(self, nid: str) -> Set[str]:
        """计算指向 nid 的所有上游（反向边）。"""
        incoming_sources: Set[str] = set()
        for src, dsts in self.edges.items():
            if nid in dsts:
                incoming_sources.add(src)
        return incoming_sources

    def remove_node(self, node_id: str, cascade: bool = False) -> None:
        """删除一个节点。
        - cascade=False：仅删除该节点，移除相关边；下游节点的 sources 中去掉该依赖。
        - cascade=True：先递归删除其规划子孙（children），再删除自己。
        """
        if node_id not in self.nodes:
            return

        # 先删除规划子孙
        if cascade:
            for child_id in list(self.nodes[node_id].children):
                self.remove_node(child_id, cascade=True)

        # 父节点关系
        parent_id = self.nodes[node_id].parent
        if parent_id and parent_id in self.nodes:
            if node_id in self.nodes[parent_id].children:
                self.nodes[parent_id].children.remove(node_id)

        # 清理上游边（src -> node_id）
        for src in list(self._incoming(node_id)):
            if src in self.edges:
                self.edges[src].discard(node_id)
        # 清理下游边（node_id -> dst）并从 dst.sources 移除
        for dst in list(self.edges.get(node_id, set())):
            if dst in self.nodes:
                if node_id in self.nodes[dst].sources:
                    self.nodes[dst].sources.remove(node_id)
        if node_id in self.edges:
            del self.edges[node_id]

        # 动态依赖关系表中移除
        if node_id in self.dynamic_dependents:
            del self.dynamic_dependents[node_id]
        for dyn, ds in list(self.dynamic_dependents.items()):
            if node_id in ds:
                ds.discard(node_id)
                self.dynamic_dependents[dyn] = ds

        # 观测删除
        if node_id in self.observations:
            del self.observations[node_id]

        # 真正删除节点
        del self.nodes[node_id]

    def remove_nodes(self, node_ids: List[str], cascade: bool = False) -> None:
        for nid in list(node_ids):
            self.remove_node(nid, cascade=cascade)

    # ---------------- 执行 & 观测 ----------------
    def update_observation(self, node_id: str, observation: Any) -> None:
        self.observations[node_id] = observation
        if node_id in self.nodes:
            # 根据观测结果设置正确的状态
            if isinstance(observation, dict) and observation.get("status") == "failed":
                self.nodes[node_id].status = "failed"
            else:
                self.nodes[node_id].status = "done"

    def set_status(self, node_id: str, status: str) -> None:
        """设置任务状态：pending|done|failed|skipped"""
        if node_id not in self.nodes:
            return
        if status not in {"pending", "done", "failed", "skipped"}:
            raise ValueError(f"invalid status: {status}")
        self.nodes[node_id].status = status

    def get_observations(self, ids: Optional[List[str]] = None) -> Dict[str, Any]:
        if ids is None:
            return dict(self.observations)
        return {i: self.observations[i] for i in ids if i in self.observations}

    # ---------------- 拓扑查询 ----------------
    def can_execute(self, nid: str) -> bool:
        """动态节点不执行；普通节点需其所有 sources（及其后续拆解产生的子树）完成。"""
        node = self.nodes[nid]
        
        # 动态节点不直接执行
        if node.dynamic:
            return False
            
        # 只有pending状态的任务可以执行（done/failed/skipped都不能再执行）
        if node.status != "pending":
            return False
            
        # 直接 sources 均需完成（含其 descendants 完成的约束通过重定向已满足）
        for s in node.sources:
            if self.nodes[s].status != "done":
                return False
        return True

    def ready_nodes(self) -> List[str]:
        return [nid for nid in self.nodes if self.can_execute(nid)]
    
    def detect_blocked_nodes(self) -> List[str]:
        """检测被阻塞的节点：依赖的任务都失败了，自己永远无法执行"""
        blocked = []
        for nid, node in self.nodes.items():
            if node.status != "pending":
                continue
            if node.dynamic:
                continue
                
            # 检查是否所有依赖都失败了
            if node.sources:
                all_sources_failed = all(
                    self.nodes[src].status == "failed" for src in node.sources
                    if src in self.nodes
                )
                if all_sources_failed:
                    blocked.append(nid)
        return blocked
    
    def mark_blocked_as_skipped(self) -> int:
        """将被阻塞的节点标记为跳过，返回标记的数量"""
        blocked = self.detect_blocked_nodes()
        for nid in blocked:
            self.set_status(nid, "skipped")
        return len(blocked)

    # ---------------- 动态节点扩展查询 ----------------
    def dynamic_can_expand(self, nid: str) -> bool:
        """
        动态节点在其所有 sources 完成后可触发拆解。
        如果动态节点已经有子节点，说明已经扩展过了，不能再次扩展。
        """
        if nid not in self.nodes:
            return False
        node = self.nodes[nid]
        if not node.dynamic:
            return False
        
        # 如果动态节点已经有子节点，说明已经扩展过了
        if node.children:
            return False
            
        for s in node.sources:
            if self.nodes[s].status != "done":
                return False
        return True

    def ready_dynamic_nodes(self) -> List[str]:
        """
        返回所有可进行拆解的动态节点ID列表。
        """
        return [nid for nid in self.nodes if self.dynamic_can_expand(nid)]

    def get_expand_inputs(self, dynamic_node_ids: List[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        获取动态节点扩展所需的前序结果。
        如果不指定 dynamic_node_ids，则自动获取所有可扩展的动态节点。
        
        返回格式：{动态节点ID: {前序节点ID: 观测结果}}
        """
        if dynamic_node_ids is None:
            dynamic_node_ids = self.ready_dynamic_nodes()
        
        expand_inputs = {}
        for dyn_id in dynamic_node_ids:
            if dyn_id not in self.nodes:
                continue
            dyn_node = self.nodes[dyn_id]
            inputs = {}
            for source_id in dyn_node.sources:
                if source_id in self.observations:
                    inputs[source_id] = self.observations[source_id]
            expand_inputs[dyn_id] = inputs
        
        return expand_inputs

    # ---------------- 动态拆解（核心） ----------------
    def expand_dynamic(self, parent_id: str, child_specs: List[Dict[str, Any]]) -> None:
        """
        在动态节点 parent_id 下增量添加子任务。
        规则：
        - 子任务默认继承 parent.sources（即 B 的子任务 D/E 依赖 A），而不是依赖 parent 本身。
        - 汇总类（聚合）子任务可显式以 D/E 为 sources。
        - 拆解后：把所有“原本依赖 parent 的节点”，其 sources 从 parent 重写为 “parent 子图的依赖叶子集”。
        """
        if parent_id not in self.nodes:
            raise KeyError(f"parent node {parent_id} not found")
        parent = self.nodes[parent_id]
        assert parent.dynamic, f"{parent_id} must be dynamic/expandable"

        # 先创建所有子节点（确保可引用到彼此）
        new_ids = {spec["id"] for spec in child_specs}
        # 规范化子任务 sources：若未显式依赖子任务集（例如聚合 F），则继承 parent.sources
        normalized: List[Dict[str, Any]] = []
        for spec in child_specs:
            spec = dict(spec)
            spec["parent"] = parent_id
            srcs = spec.get("sources", [])
            # 如果 sources 为空，或把 parent 当作 source（需要重写），则改为继承 parent.sources
            if (not srcs) or (parent_id in srcs):
                spec["sources"] = list(parent.sources)
            else:
                # 判断是否为聚合任务（sources 全在新子集中），这类保持显式依赖
                if not set(srcs).issubset(new_ids):
                    # 也允许 union 上 parent.sources（有时既要依赖 D/E，也要引用 A 的上下文）
                    spec["sources"] = list(
                        dict.fromkeys(list(parent.sources) + list(srcs))
                    )
            normalized.append(spec)

        # 添加子节点与边
        self.add_nodes(normalized)

        # 重定向所有原本依赖 parent 的下游节点到“叶子”
        self._redirect_downstreams_to_dynamic_leaves(parent_id)

    def _planning_descendants(self, root_id: str) -> Set[str]:
        """基于 parent/children 的分层关系，取 root 的所有规划子孙（不含 root）。"""
        out: Set[str] = set()
        stack: List[str] = list(self.nodes[root_id].children)
        while stack:
            cur = stack.pop()
            out.add(cur)
            stack.extend(self.nodes[cur].children)
        return out

    def _dynamic_leaves_by_dependency(self, root_id: str) -> Set[str]:
        """
        在 root 的规划子图（所有规划子孙）内部，基于依赖边计算“叶子”：
        即在该子图内没有出边指向子图内其他节点的节点。
        """
        sub = self._planning_descendants(root_id)
        if not sub:
            return set()
        leaves: Set[str] = set()
        for nid in sub:
            outs = self.edges.get(nid, set())
            if not any(dst in sub for dst in outs):
                leaves.add(nid)
        return leaves

    def _redirect_downstreams_to_dynamic_leaves(self, root_id: str) -> None:
        """
        将所有“原本依赖 root（动态占位）”的节点的 sources，替换为
        当前 root 子图的依赖叶子集：
          - 如果叶子为空（尚未拆解），保持 root 作为依赖；
          - 否则：从 sources 中移除 root 以及 root 子图内的非叶子节点，加入叶子，并维护 edges。
        """
        sub = self._planning_descendants(root_id)
        leaves = self._dynamic_leaves_by_dependency(root_id)
        dependents = self.dynamic_dependents.get(root_id, set()).copy()

        for yid in dependents:
            if yid not in self.nodes:
                continue
            y = self.nodes[yid]
            if not leaves:
                # 还没拆出任何子节点，保持依赖 root（占位阻塞后续执行）
                if root_id not in y.sources:
                    y.sources.append(root_id)
                    self.edges.setdefault(root_id, set()).add(yid)
                continue

            # 移除 root 与 sub 中的非叶子
            old_sources = list(y.sources)
            new_sources: List[str] = []
            for s in old_sources:
                if s == root_id:
                    # drop
                    if yid in self.edges.get(s, set()):
                        self.edges[s].discard(yid)
                    continue
                if s in sub and s not in leaves:
                    # 这个是子图内的中间节点，移除
                    if yid in self.edges.get(s, set()):
                        self.edges[s].discard(yid)
                    continue
                new_sources.append(s)

            # 添加叶子
            for leaf in leaves:
                if leaf not in new_sources:
                    new_sources.append(leaf)
                    self.edges.setdefault(leaf, set()).add(yid)

            y.sources = new_sources

    # ---------------- 执行输入收集 ----------------
    def execution_inputs(self, nid: str) -> Dict[str, Any]:
        """
        返回执行 nid 时需要的 observations：
        - 对于每个 source：
          - 若 source 为动态占位（不会有 obs），则已在重定向中被替换成叶子，所以只取叶子 obs；
          - 否则取该 source 自身的 obs（以及它的后续拆解已通过重定向体现为额外 sources）。
        """
        obs: Dict[str, Any] = {}
        for s in self.nodes[nid].sources:
            if s in self.observations:
                obs[s] = self.observations[s]
        return obs

    # ---------------- JSON 更新入口 ----------------
    def apply_update(self, update: Dict[str, Any]) -> None:
        """按 JSON 指令进行增量更新。
        支持：
        - {"add_nodes": [...]}  节点增量添加/合并
        - {"add_edges": [[src, dst], ...]}  增量添加依赖边
        - {"remove_nodes": [id1, id2, ...]}  删除节点（非级联）
        - {"remove_nodes_cascade": [id3, ...]}  级联删除（含子孙）
        - {"status": {"X": "done", ...}}  批量状态设置
        - {"observations": {"X": {...}, ...}}  批量观测更新（并置为 done）
        """
        if not update:
            return
        if "title" in update:
            self.title = update["title"]
        if "thought" in update:
            self.thought = update["thought"]
        if "add_nodes" in update:
            self.add_nodes(list(update["add_nodes"]))
        if "add_edges" in update:
            for src, dst in list(update["add_edges"]):
                self.add_edge(src, dst)
        if "remove_nodes" in update:
            self.remove_nodes(list(update["remove_nodes"]), cascade=False)
        if "remove_nodes_cascade" in update:
            self.remove_nodes(list(update["remove_nodes_cascade"]), cascade=True)
        if "status" in update:
            for nid, st in dict(update["status"]).items():
                self.set_status(nid, st)
        if "observations" in update:
            for nid, obs in dict(update["observations"]).items():
                self.update_observation(nid, obs)

    # ---------------- 快照/展示 ----------------
    def snapshot(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "thought": self.thought,
            "nodes": {
                nid: {
                    "id": n.id,
                    "type": n.type,
                    "title": n.title,
                    "thoughts": n.thoughts,
                    "sources": list(n.sources),
                    "parent": n.parent,
                    "children": list(n.children),
                    "dynamic": n.dynamic,
                    "status": n.status,
                }
                for nid, n in self.nodes.items()
            },
            "edges": {k: list(v) for k, v in self.edges.items()},
            # "observations": dict(self.observations),
            "dynamic_dependents": {k: list(v) for k, v in self.dynamic_dependents.items()},
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为可序列化的字典格式"""
        return {
            "title": self.title,
            "thought": self.thought,
            "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()},
            "edges": {k: list(v) for k, v in self.edges.items()},
            "observations": self.observations,
            "dynamic_dependents": {k: list(v) for k, v in self.dynamic_dependents.items()},
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlanManager':
        """从字典格式创建PlanManager实例"""
        instance = cls()
        
        # 恢复title和thought
        instance.title = data.get("title", "")
        instance.thought = data.get("thought", "")
        
        # 恢复nodes
        for nid, node_data in data.get("nodes", {}).items():
            instance.nodes[nid] = Node.from_dict(node_data)
        
        # 恢复edges
        for src, dsts in data.get("edges", {}).items():
            instance.edges[src] = set(dsts)
        
        # 恢复observations
        instance.observations = data.get("observations", {})
        
        # 恢复dynamic_dependents
        for dyn_id, deps in data.get("dynamic_dependents", {}).items():
            instance.dynamic_dependents[dyn_id] = set(deps)
        
        return instance
    
    def __getstate__(self) -> Dict[str, Any]:
        """支持pickle序列化"""
        return self.to_dict()
    
    def __setstate__(self, state: Dict[str, Any]) -> None:
        """支持pickle反序列化"""
        restored = PlanManager.from_dict(state)
        self.title = restored.title
        self.thought = restored.thought
        self.nodes = restored.nodes
        self.edges = restored.edges
        self.observations = restored.observations
        self.dynamic_dependents = restored.dynamic_dependents 