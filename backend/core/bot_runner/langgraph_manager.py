"""
Graph Manager for LanggraphAgentRunner
负责管理graph的缓存、创建、过期清理等逻辑
"""

import logging
import threading
import time
from typing import Optional, Dict, Tuple

from langgraph.graph.state import CompiledStateGraph

logger = logging.getLogger(__name__)


class GraphManager:
    """Graph管理器，负责graph的缓存、创建、过期清理等"""
    
    def __init__(self, expiration_seconds: int = 86400, cleanup_interval: int = 3600):
        """
        初始化Graph管理器
        
        Args:
            expiration_seconds: graph缓存过期时间（秒），默认1天
            cleanup_interval: 后台清理间隔（秒），默认1小时
        """
        self.expiration_seconds = expiration_seconds
        self.cleanup_interval = cleanup_interval
        
        # 缓存结构: thread_id -> (graph, timestamp)
        self._cache: Dict[str, Tuple[CompiledStateGraph, float]] = {}
        
        # 后台清理线程控制
        self._cleanup_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()  # 可重入锁，支持嵌套调用
        
        # 启动后台清理线程
        self._start_background_cleanup()
    
    def get_graph(self, thread_id: str, graph_factory_func, *args, **kwargs) -> CompiledStateGraph:
        """
        获取graph，如果缓存中没有或已过期则创建新的
        
        Args:
            thread_id: 线程ID
            graph_factory_func: 创建graph的工厂函数
            *args, **kwargs: 传递给工厂函数的参数
            
        Returns:
            CompiledStateGraph: 可用的graph实例
        """
        with self._lock:
            # 检查缓存中是否有有效的graph
            cached_graph = self._get_valid_graph_from_cache(thread_id)
            if cached_graph:
                # 更新最后使用时间戳
                self._update_timestamp(thread_id)
                return cached_graph
            
            # 缓存中没有或已过期，创建新的graph
            new_graph = graph_factory_func(*args, **kwargs)
            
            # 缓存新创建的graph
            self._set_graph_in_cache(thread_id, new_graph)
            
            return new_graph
    
    def _is_graph_expired(self, timestamp: float) -> bool:
        """检查指定时间戳的graph是否已过期"""
        return time.time() - timestamp > self.expiration_seconds
    
    def _get_valid_graph_from_cache(self, thread_id: str) -> Optional[CompiledStateGraph]:
        """从缓存中获取有效的graph，如果过期或不存在则返回None"""
        # 注意：此方法应该在锁的保护下调用
        if thread_id not in self._cache:
            return None
        
        graph, timestamp = self._cache[thread_id]
        
        if self._is_graph_expired(timestamp):
            # 移除过期graph
            self._remove_graph_safely(thread_id)
            return None
        
        return graph
    
    def _set_graph_in_cache(self, thread_id: str, graph: CompiledStateGraph) -> None:
        """将graph存储到缓存中，并记录当前时间戳"""
        # 注意：此方法应该在锁的保护下调用
        current_time = time.time()
        self._cache[thread_id] = (graph, current_time)
    
    def _update_timestamp(self, thread_id: str) -> None:
        """更新graph的最后使用时间戳"""
        # 注意：此方法应该在锁的保护下调用
        if thread_id in self._cache:
            graph, _ = self._cache[thread_id]
            current_time = time.time()
            self._cache[thread_id] = (graph, current_time)
    
    def _remove_graph_safely(self, thread_id: str) -> bool:
        """
        安全地移除graph，直接删除缓存条目
        
        Args:
            thread_id: 线程ID
            
        Returns:
            bool: 是否成功移除
        """
        # 注意：此方法应该在锁的保护下调用
        if thread_id not in self._cache:
            return False
        
        # 直接删除缓存条目，让Python的垃圾回收机制处理graph对象
        # 这样可以避免在对象正在使用时强制删除
        del self._cache[thread_id]
        
        return True
    
    def _cleanup_expired_graphs(self) -> int:
        """清理过期的graph缓存，返回被清理的数量"""
        # 注意：此方法应该在锁的保护下调用
        current_time = time.time()
        cleaned_count = 0
        
        # 清理过期的graph
        expired_threads = [
            thread_id for thread_id, (_, timestamp) in self._cache.items()
            if current_time - timestamp > self.expiration_seconds
        ]

        for thread_id in expired_threads:
            if self._remove_graph_safely(thread_id):
                cleaned_count += 1
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} expired graphs")
        
        return cleaned_count
    
    def _start_background_cleanup(self) -> None:
        """启动后台清理线程"""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            return
        
        def cleanup_worker():
            """后台清理工作函数"""
            while True:
                try:
                    # 使用锁保护清理操作
                    with self._lock:
                        self._cleanup_expired_graphs()
                    
                    # 等待下次清理周期
                    time.sleep(self.cleanup_interval)
                    
                except Exception as e:
                    logger.error(f"Cleanup thread error: {e}")
                    # 等待一段时间后重试
                    time.sleep(60)
        
        self._cleanup_thread = threading.Thread(
            target=cleanup_worker, 
            daemon=True, 
            name="GraphCacheCleanup"
        )
        self._cleanup_thread.start()
    
    def _estimate_cache_size(self) -> int:
        """估算缓存占用的内存大小（字节）"""
        # 注意：此方法应该在锁的保护下调用
        # 这是一个简化的估算，实际大小可能因graph复杂度而异
        estimated_size = 0
        for thread_id, (graph, timestamp) in self._cache.items():
            # 基础开销：thread_id字符串 + timestamp + 对象引用
            estimated_size += len(thread_id.encode('utf-8')) + 8 + 64
            # graph对象大小估算（如果graph为None，则不计算）
            if graph is not None:
                estimated_size += 1024  # 假设每个graph约1KB
        
        return estimated_size


# 全局Graph管理器实例
_graph_manager: Optional[GraphManager] = None


def get_graph_manager(expiration_seconds: int = 86400, cleanup_interval: int = 3600) -> GraphManager:
    """
    获取全局Graph管理器实例
    
    Args:
        expiration_seconds: graph缓存过期时间（秒）
        cleanup_interval: 后台清理间隔（秒）
        
    Returns:
        GraphManager: 全局Graph管理器实例
    """
    global _graph_manager
    
    if _graph_manager is None:
        _graph_manager = GraphManager(expiration_seconds, cleanup_interval)
    
    return _graph_manager
