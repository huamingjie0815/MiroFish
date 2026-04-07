"""
知识图谱适配器
支持 Zep Cloud 和 Graphiti (本地) 两种模式

使用方式:
    from app.services.kg_adapter import get_knowledge_graph_adapter

    kg = get_knowledge_graph_adapter()
    kg.add_episode(graph_id="xxx", text="hello")
    kg.search(graph_id="xxx", query="hello")
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import logging

from ..config import Config
from graphiti_core.embedder import EmbedderClient as EmbeddingClient

logger = logging.getLogger(__name__)


class KnowledgeGraphAdapter(ABC):
    """知识图谱适配器抽象基类"""

    @abstractmethod
    def create_graph(self, graph_id: str, name: str = None) -> Any:
        """创建图谱"""
        pass

    @abstractmethod
    def add_episode(self, graph_id: str, text: str, **kwargs) -> Any:
        """添加单条内容"""
        pass

    @abstractmethod
    def add_episodes_batch(self, graph_id: str, texts: List[str]) -> List[Any]:
        """批量添加内容"""
        pass

    @abstractmethod
    def get_episode(self, episode_uuid: str) -> Any:
        """获取单个 episode"""
        pass

    @abstractmethod
    def search(self, graph_id: str, query: str, limit: int = 10, scope: str = "all", reranker: str = None) -> List[Dict]:
        """搜索"""
        pass

    @abstractmethod
    def get_nodes(self, graph_id: str, limit: int = 100, cursor: str = None) -> List[Any]:
        """获取节点"""
        pass

    @abstractmethod
    def get_node(self, node_uuid: str) -> Any:
        """获取单个节点"""
        pass

    @abstractmethod
    def get_node_edges(self, node_uuid: str) -> List[Dict]:
        """获取节点的所有边"""
        pass

    @abstractmethod
    def get_edges(self, graph_id: str, limit: int = 100, cursor: str = None) -> List[Any]:
        """获取边"""
        pass

    @abstractmethod
    def delete(self, graph_id: str) -> bool:
        """删除图谱"""
        pass

    @abstractmethod
    def set_ontology(self, graph_id: str, ontology: Dict) -> bool:
        """设置本体"""
        pass

    @abstractmethod
    def get_graph_info(self, graph_id: str) -> Dict:
        """获取图谱信息"""
        pass


class ZepCloudAdapter(KnowledgeGraphAdapter):
    """Zep Cloud 适配器"""

    def __init__(self, api_key: str = None):
        from zep_cloud.client import Zep
        self.api_key = api_key or Config.ZEP_API_KEY
        if not self.api_key:
            raise ValueError("ZEP_API_KEY 未配置")
        self.client = Zep(api_key=self.api_key)
        logger.info("ZepCloudAdapter 初始化完成")

    def create_graph(self, graph_id: str, name: str = None) -> Any:
        return self.client.graph.create(graph_id=graph_id, name=name or graph_id)

    def add_episode(self, graph_id: str, text: str, **kwargs) -> Any:
        return self.client.graph.add(graph_id=graph_id, type="text", data=text)

    def add_episodes_batch(self, graph_id: str, texts: List[str]) -> List[Any]:
        from zep_cloud.types import EpisodeData
        episodes = [EpisodeData(data=t, type="text") for t in texts]
        return self.client.graph.add_batch(episodes=episodes, graph_id=graph_id)

    def get_episode(self, episode_uuid: str) -> Any:
        return self.client.graph.episode.get(uuid_=episode_uuid)

    def search(self, graph_id: str, query: str, limit: int = 10, scope: str = "all", reranker: str = None):
        """搜索图谱

        返回 GraphSearchResults 对象：
        - scope="edges": 结果在 .edges 中
        - scope="nodes": 结果在 .nodes 中
        - scope="all": 结果同时在 .edges 和 .nodes 中
        """
        try:
            result = self.client.graph.search(graph_id=graph_id, query=query, limit=limit, scope=scope, reranker=reranker)
            logger.info(f"[ZepCloud search] query={query}, edges={len(result.edges) if hasattr(result, 'edges') and result.edges else 0}, nodes={len(result.nodes) if hasattr(result, 'nodes') and result.nodes else 0}")
            return result
        except Exception as e:
            logger.error(f"[ZepCloud search] API调用失败: {e}")
            # 返回空的 GraphSearchResults
            from zep_cloud.types.graph_search_results import GraphSearchResults
            return GraphSearchResults(edges=[], nodes=[], episodes=[])

    def get_nodes(self, graph_id: str, limit: int = 100, cursor: str = None) -> List[Any]:
        kwargs = {"limit": limit}
        if cursor:
            kwargs["uuid_cursor"] = cursor
        return self.client.graph.node.get_by_graph_id(graph_id=graph_id, **kwargs)

    def get_node(self, node_uuid: str) -> Any:
        return self.client.graph.node.get(uuid_=node_uuid)

    def get_node_edges(self, node_uuid: str) -> List[Dict]:
        edges = self.client.graph.node.get_entity_edges(node_uuid=node_uuid)
        return [e.model_dump() if hasattr(e, 'model_dump') else e for e in edges]

    def get_edges(self, graph_id: str, limit: int = 100, cursor: str = None) -> List[Any]:
        kwargs = {"limit": limit}
        if cursor:
            kwargs["uuid_cursor"] = cursor
        return self.client.graph.edge.get_by_graph_id(graph_id=graph_id, **kwargs)

    def delete(self, graph_id: str) -> bool:
        self.client.graph.delete(graph_id=graph_id)
        return True

    def set_ontology(self, graph_id: str, ontology: Dict) -> bool:
        entities = ontology.get('entities', {})
        edges = ontology.get('edges', {})
        self.client.graph.set_ontology(
            entities=entities,
            edges=edges,
            graph_ids=[graph_id]
        )
        return True

    def get_graph_info(self, graph_id: str) -> Dict:
        # Zep Cloud 没有直接的图谱信息 API，返回基本信息
        return {"graph_id": graph_id}


# 自定义 Embedder，支持可配置的批处理大小
class SingleEmbeddingEmbedder(EmbeddingClient):
    """自定义 embedder，支持可配置的批处理大小

    Args:
        base: 基础 embedder
        batch_size: 批量大小，默认 10（阿里百炼支持），设为 1 则逐个处理
    """

    def __init__(self, base, batch_size: int = 10):
        self.base = base
        self.batch_size = batch_size

    async def create(self, input_data):
        # 如果是列表，根据列表长度决定返回格式
        if isinstance(input_data, list):
            if len(input_data) == 1:
                return await self.base.create(input_data[0])
            elif len(input_data) == 0:
                return await self.base.create("")
            else:
                # 多个输入，调用批量处理
                return await self.create_batch(input_data)
        return await self.base.create(input_data)

    async def create_batch(self, input_data_list):
        # 逐个处理，避免兼容性问题
        results = []
        for text in input_data_list:
            embedding = await self.base.create(text)
            results.append(embedding)
        return results


class GraphitiAdapter(KnowledgeGraphAdapter):
    """Graphiti 适配器 - 本地部署

    注意：类级别的 event loop 会在应用退出时自动释放，
    不需要手动关闭。长时间运行的服务器不需要关闭 event loop。
    """

    # 类级别的 event loop，供所有实例共享
    _event_loop = None

    def __init__(self):
        import os
        import asyncio
        from graphiti_core import Graphiti
        from graphiti_core.llm_client.config import LLMConfig
        from ..utils.graphiti_llm_client import CompatibleGraphitiClient
        from graphiti_core.embedder import OpenAIEmbedder, OpenAIEmbedderConfig

        if not all([Config.NEO4J_URI, Config.NEO4J_USER, Config.NEO4J_PASSWORD]):
            raise ValueError("Neo4j 配置不完整，请检查 NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD")

        # 获取 API Key（优先使用独立配置，其次使用 LLM 配置）
        api_key = Config.LLM_API_KEY or Config.OPENAI_API_KEY
        llm_base_url = Config.LLM_BASE_URL

        # 嵌入模型独立配置
        embedding_api_key = Config.EMBEDDING_API_KEY or api_key
        embedding_base_url = Config.EMBEDDING_BASE_URL or llm_base_url

        if not api_key:
            raise ValueError("请配置 LLM_API_KEY")

        # 设置环境变量（Graphiti 内部组件会读取）
        os.environ['OPENAI_API_KEY'] = api_key
        os.environ['OPENAI_BASE_URL'] = llm_base_url

        # 配置 LLM 客户端（支持 OpenAI 兼容 API）
        llm_config = LLMConfig(
            api_key=api_key,
            base_url=llm_base_url,
            model=Config.LLM_MODEL_NAME,
            small_model=Config.LLM_MODEL_NAME,  # 使用相同模型
        )
        llm_client = CompatibleGraphitiClient(config=llm_config)

        # 配置 Embedder 客户端（可独立配置）
        # 注意：一些 embedding API 不支持批量请求
        # 因此我们创建一个自定义包装器来确保每次只处理单个文本
        embedder_config = OpenAIEmbedderConfig(
            api_key=embedding_api_key,
            base_url=embedding_base_url,
            embedding_model=Config.EMBEDDING_MODEL,
            embedding_dim=Config.EMBEDDING_DIM,
        )
        logger.debug("embedding_base_url:" + embedding_base_url)
        base_embedder = OpenAIEmbedder(config=embedder_config)

        # 使用自定义包装器，支持可配置的批处理大小
        # 默认 batch_size=10（阿里百炼支持），可在 Config 中配置
        batch_size = getattr(Config, 'EMBEDDING_BATCH_SIZE', 10)
        embedder_client = SingleEmbeddingEmbedder(base_embedder, batch_size=batch_size)
        logger.debug(f"model: {Config.EMBEDDING_MODEL}, batch_size: {batch_size}")

        self.client = Graphiti(
            uri=Config.NEO4J_URI,
            user=Config.NEO4J_USER,
            password=Config.NEO4J_PASSWORD,
            llm_client=llm_client,
            embedder=embedder_client,
            cross_encoder=None,  # 禁用 reranker，需要时可配置
        )
        # graph_id 到 group 的映射（Graphiti 使用 group 区分不同的图）
        self._graph_id_to_group: Dict[str, str] = {}

        # 使用同步驱动避免 asyncio 事件循环冲突
        from neo4j import GraphDatabase
        self._sync_driver = GraphDatabase.driver(
            Config.NEO4J_URI,
            auth=(Config.NEO4J_USER, Config.NEO4J_PASSWORD)
        )

        # 初始化数据库索引
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.client.build_indices_and_constraints())
            # 不关闭 loop，保存起来供后续使用
            GraphitiAdapter._event_loop = loop
            logger.info("Graphiti 数据库索引初始化完成")
        except Exception as e:
            logger.warning(f"数据库索引初始化警告: {e}")

        logger.info("GraphitiAdapter 初始化完成")

    def _run_async(self, coro, timeout: int = 300):
        """同步调用异步方法的包装器，使用类级别的 event loop，带超时保护"""
        import asyncio
        import concurrent.futures

        # 使用类级别的 event loop
        if GraphitiAdapter._event_loop is None or GraphitiAdapter._event_loop.is_closed():
            GraphitiAdapter._event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(GraphitiAdapter._event_loop)

        # 使用线程池执行，避免阻塞
        def run_in_loop():
            return GraphitiAdapter._event_loop.run_until_complete(coro)

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(run_in_loop)
                return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            logger.error(f"Graphiti 操作超时 ({timeout}秒)")
            raise TimeoutError(f"Graphiti operation timed out after {timeout} seconds")
        except Exception as e:
            logger.error(f"Graphiti 操作失败: {str(e)}")
            raise

    def _get_group(self, graph_id: str) -> str:
        """获取或创建 group"""
        if graph_id not in self._graph_id_to_group:
            self._graph_id_to_group[graph_id] = graph_id
        return self._graph_id_to_group[graph_id]

    def create_graph(self, graph_id: str, name: str = None) -> Any:
        # Graphiti 不需要预创建图，通过 group 区分
        self._graph_id_to_group[graph_id] = graph_id

        # 创建 Group 节点
        with self._sync_driver.session() as session:
            session.run("""
                MERGE (g:Group {name: $name})
                SET g.created_at = datetime()
            """, name=graph_id)

        logger.info(f"Graphiti: 标记图谱 {graph_id}")
        return {"status": "ok", "graph_id": graph_id}

    def add_episode(self, graph_id: str, text: str, **kwargs) -> Any:
        """使用同步驱动添加 episode"""
        import uuid
        from datetime import datetime, timezone

        group = self._get_group(graph_id)
        episode_uuid = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # 直接使用同步驱动创建 episode
        with self._sync_driver.session() as session:
            query = """
            CREATE (e:Episodic {
                uuid: $uuid,
                name: $name,
                content: $content,
                created_at: $created_at,
                valid_at: $valid_at,
                group_id: $group_id,
                source: 'text',
                episode_type: 'text'
            })
            RETURN e
            """
            result = session.run(
                query,
                uuid=episode_uuid,
                name=f"episode_{now.strftime('%Y%m%d%H%M%S')}",
                content=text,
                created_at=now,
                valid_at=now,
                group_id=group
            )
            record = result.single()
            return {"uuid": episode_uuid, "name": record["e"]["name"]} if record else None

    def add_episodes_batch(self, graph_id: str, texts: List[str], batch_size: int = 10) -> List[Any]:
        """批量添加内容，使用 Graphiti 原生的 add_episode API"""
        from datetime import datetime, timezone
        from graphiti_core.nodes import EpisodeType

        results = []
        group = self._get_group(graph_id)
        now = datetime.now(timezone.utc)

        # 获取实体类型（如果有的话）
        entity_types = getattr(self, '_entity_types', None)
        if entity_types:
            logger.info(f"Graphiti: 使用 {len(entity_types)} 个实体类型进行提取: {list(entity_types.keys())}")

        # 使用 Graphiti 原生的 add_episode 方法
        # 它会自动：1. 用 embedder 做嵌入 2. 用 LLM 提取实体和关系
        for i, text in enumerate(texts):
            episode_name = f"episode_{now.strftime('%Y%m%d%H%M%S')}_{i}"

            try:
                # 调用 Graphiti 原生 API，传入 entity_types
                result = self._run_async(
                    self.client.add_episode(
                        name=episode_name,
                        episode_body=text,
                        source_description="MiroFish document",
                        reference_time=now,
                        source=EpisodeType.text,
                        group_id=group,
                        entity_types=entity_types,  # 传入实体类型定义
                    )
                )

                # 从返回结果中获取 episode 的 uuid
                episode_uuid = None
                if result and hasattr(result, 'episode'):
                    episode_uuid = getattr(result.episode, 'uuid_', None) or getattr(result.episode, 'uuid', None)

                logger.info(f"Graphiti 原生添加 episode {i+1}/{len(texts)}: {episode_uuid}")
                results.append({"uuid": episode_uuid, "name": episode_name})

            except Exception as e:
                logger.error(f"添加 episode 失败: {str(e)}")
                results.append({"uuid": None, "name": episode_name, "error": str(e)})

        logger.info(f"Graphiti 实体全部构建完成: {graph_id}, 共 {len(results)} 条")
        return results

    def get_episode(self, episode_uuid: str) -> Any:
        """使用同步驱动获取 episode"""
        with self._sync_driver.session() as session:
            query = """
            MATCH (e:Episodic {uuid: $uuid})
            RETURN e.content as content, e.created_at as created_at,
                   e.valid_at as valid_at, e.uuid as uuid,
                   e.name as name, e.group_id as group_id
            """
            result = session.run(query, uuid=episode_uuid)
            record = result.single()
            if record:
                data = dict(record)
                # Graphiti 模式下添加是同步的，返回 processed=True 表示已完成
                data['processed'] = True
                logger.debug(f"[get_episode] uuid={episode_uuid}, processed=True")
                return data
            logger.warning(f"[get_episode] uuid={episode_uuid}, 未找到 episode")
            return None

    def search(self, graph_id: str, query: str, limit: int = 10, scope: str = "all", reranker: str = None):
        logger.info(f"[GraphitiAdapter.search] 调用")
        """使用同步驱动搜索

        返回兼容对象格式：
        - scope="edges": 返回带 .edges 属性的对象
        - scope="nodes": 返回带 .nodes 属性的对象
        - scope="all": 返回带 .edges 和 .nodes 属性的对象
        """
        from dataclasses import dataclass, field
        import re

        @dataclass
        class SearchResult:
            edges: list = field(default_factory=list)
            nodes: list = field(default_factory=list)

        group = self._get_group(graph_id)
        result = SearchResult()

        # 从查询中提取关键词（移除"关于...的所有信息"等前缀）
        search_keyword = query
        if '的' in search_keyword:
            match = re.search(r'关于(.+?)的', search_keyword)
            if match:
                search_keyword = match.group(1).strip()
        if len(search_keyword) > 10:
            search_keyword = search_keyword[:10]

        with self._sync_driver.session() as session:
            # 搜索 Episodes 作为事实来源
            episode_query = """
            MATCH (e:Episodic {group_id: $gid})
            WHERE e.content CONTAINS $search
            RETURN e.content as content, e.uuid as uuid, e.name as name
            """
            episode_result = session.run(
                episode_query,
                gid=group,
                search=search_keyword
            )

            episodes = [{"content": r["content"], "uuid": r["uuid"], "name": r["name"]} for r in episode_result]

            # 根据 scope 返回对应格式
            if scope in ("edges", "all"):
                # 将 episodes 内容转为 fact 格式
                for ep in episodes:
                    class Edge:
                        def __init__(self, fact):
                            self.fact = fact
                    result.edges.append(Edge(ep.get("content", "")))

            if scope in ("nodes", "all"):
                # 搜索相关实体节点
                entity_query = """
                MATCH (e:Entity {group_id: $gid})
                WHERE e.name CONTAINS $search OR e.summary CONTAINS $search
                RETURN e.uuid as uuid_, e.name as name, e.summary as summary
                """
                entity_result = session.run(
                    entity_query,
                    gid=group,
                    search=search_keyword
                )

                for ent in entity_result:
                    class Node:
                        def __init__(self, name, summary):
                            self.name = name
                            self.summary = summary if summary else ""
                    result.nodes.append(Node(ent["name"], ent.get("summary")))

        return result

    def get_nodes(self, graph_id: str, limit: int = 100, cursor: str = None) -> List[Any]:
        """通过同步驱动查询实体节点"""
        with self._sync_driver.session() as session:
            # Graphiti 使用 group_id 属性来区分不同的图谱
            query = """
            MATCH (e:Entity {group_id: $group_id})
            RETURN e.uuid as uuid_, e.name as name, labels(e) as labels,
                   e.summary as summary, e.created_at as created_at
            LIMIT $limit
            """
            result = session.run(query, group_id=graph_id, limit=limit)
            nodes = [dict(record) for record in result]
            logger.info(f"[get_nodes] graph_id={graph_id}, 查询到 {len(nodes)} 个节点")

            # 转换格式以兼容前端
            for node in nodes:
                if 'attributes' not in node:
                    node['attributes'] = {}

                # 从标签中提取实体类型（第一个非 Entity 的标签）
                labels = node.get('labels', [])
                found_type = None
                for label in labels:
                    if label and label != 'Entity':
                        found_type = label
                        break

                if found_type:
                    node['labels'] = [found_type]
                    node['attributes']['entity_type'] = found_type
                else:
                    # 如果没有具体标签，使用通用 Entity 类型
                    node['labels'] = ['Entity']
                    node['attributes']['entity_type'] = 'Entity'

            return nodes

    def get_node(self, node_uuid: str) -> Any:
        """通过同步驱动获取单个节点"""
        with self._sync_driver.session() as session:
            query = """
            MATCH (e:Entity {uuid: $uuid})
            RETURN e.uuid as uuid_, e.name as name, labels(e) as labels,
                   e.summary as summary, e.created_at as created_at
            """
            result = session.run(query, uuid=node_uuid)
            record = result.single()
            if record:
                node = dict(record)
                if 'attributes' not in node:
                    node['attributes'] = {}
                return node
            return None

    def get_node_edges(self, node_uuid: str) -> List[Dict]:
        """通过同步驱动获取节点的所有边"""
        with self._sync_driver.session() as session:
            query = """
            MATCH (e1:Entity {uuid: $uuid})-[r]-(e2:Entity)
            RETURN r.uuid as uuid_, type(r) as name, r.fact as fact,
                   e1.uuid as source_node_uuid, e2.uuid as target_node_uuid,
                   e1.name as source_node_name, e2.name as target_node_name,
                   r.created_at as created_at
            """
            result = session.run(query, uuid=node_uuid)
            edges = [dict(record) for record in result]
            for edge in edges:
                edge["fact_type"] = edge.get("fact_type") or edge.get("name", "")
            return edges

    def get_edges(self, graph_id: str, limit: int = 100, cursor: str = None) -> List[Any]:
        """通过同步驱动查询边"""
        with self._sync_driver.session() as session:
            query = """
            MATCH (e1:Entity {group_id: $group_id})-[r]-(e2:Entity {group_id: $group_id})
            RETURN r.uuid as uuid_, type(r) as name, r.fact as fact,
                   e1.uuid as source_node_uuid, e2.uuid as target_node_uuid,
                   e1.name as source_node_name, e2.name as target_node_name,
                   r.created_at as created_at, r.valid_at as valid_at,
                   r.invalid_at as invalid_at, r.expired_at as expired_at
            LIMIT $limit
            """
            result = session.run(query, group_id=graph_id, limit=limit)
            edges = [dict(record) for record in result]
            # 兼容前端格式
            for edge in edges:
                if 'attributes' not in edge:
                    edge['attributes'] = {}
                if 'episodes' not in edge:
                    edge['episodes'] = []
                edge['fact_type'] = edge.get('fact_type') or edge.get('name', '')
            return edges

    def delete(self, graph_id: str) -> bool:
        """使用同步驱动删除图谱"""
        with self._sync_driver.session() as session:
            # 删除关联边（使用 group_id 属性）
            session.run("""
                MATCH (e1:Entity)-[r]-(e2:Entity)
                WHERE e1.group_id = $group_id OR e2.group_id = $group_id
                DELETE r
            """, group_id=graph_id)
            # 删除实体节点（使用 group_id 属性）
            session.run("""
                MATCH (e:Entity {group_id: $group_id})
                DELETE e
            """, group_id=graph_id)

        if graph_id in self._graph_id_to_group:
            del self._graph_id_to_group[graph_id]

        logger.info(f"Graphiti: 删除图谱 {graph_id}")
        return True

    def set_ontology(self, graph_id: str, ontology: Dict) -> bool:
        """设置实体类型（Graphiti 模式）"""
        import warnings
        from typing import Optional
        from pydantic import Field
        from graphiti_core.nodes import EntityNode

        # graph_builder.set_ontology 已经把 ontology 转换成 Pydantic 类
        # 格式: {'entities': {类名: 类}, 'edges': {...}}
        entity_types = {}

        if ontology.get("entities") and isinstance(ontology.get("entities"), dict):
            entities = ontology.get("entities", {})
            for name, entity_class in entities.items():
                entity_types[name] = entity_class
            logger.info(f"Graphiti: 使用已处理的实体类型，共 {len(entity_types)} 个")
        else:
            logger.warning(f"Graphiti: ontology 格式异常: {list(ontology.keys())}")

        # 存储到实例变量
        self._entity_types = entity_types

        return True

    def get_graph_info(self, graph_id: str) -> Dict:
        """使用同步驱动获取图谱信息"""
        with self._sync_driver.session() as session:
            # 统计节点数量 - 使用 group_id 属性
            node_result = session.run("""
                MATCH (e:Entity {group_id: $group_id})
                RETURN count(e) as count
            """, group_id=graph_id)
            node_count = node_result.single()["count"] if node_result.single() else 0

            # 统计边数量 - 使用 group_id 属性
            edge_result = session.run("""
                MATCH (e1:Entity {group_id: $group_id})-[r]-(e2:Entity {group_id: $group_id})
                RETURN count(r) as count
            """, group_id=graph_id)
            edge_count = edge_result.single()["count"] if edge_result.single() else 0

        return {
            "graph_id": graph_id,
            "node_count": node_count,
            "edge_count": edge_count,
        }

    def _result_to_dict(self, result) -> Dict:
        if hasattr(result, 'model_dump'):
            return result.model_dump()
        elif hasattr(result, 'dict'):
            return result.dict()
        return {}


# 全局缓存
_adapter_cache: Optional[KnowledgeGraphAdapter] = None


def get_knowledge_graph_adapter(force_refresh: bool = False) -> KnowledgeGraphAdapter:
    """
    获取知识图谱适配器实例

    Args:
        force_refresh: 是否强制刷新缓存

    Returns:
        KnowledgeGraphAdapter: 适配器实例
    """
    global _adapter_cache

    if _adapter_cache is not None and not force_refresh:
        return _adapter_cache

    mode = Config.KNOWLEDGE_GRAPH_MODE
    logger.info(f"[kg_adapter] 使用模式: {mode}")

    if mode == 'local':
        _adapter_cache = GraphitiAdapter()
    elif mode == 'cloud':
        _adapter_cache = ZepCloudAdapter()
    else:
        raise ValueError(f"未知的 KNOWLEDGE_GRAPH_MODE: {mode}")

    return _adapter_cache


def reset_adapter():
    """重置适配器缓存"""
    global _adapter_cache
    _adapter_cache = None
