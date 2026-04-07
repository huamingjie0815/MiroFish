# Zep Cloud 迁移到 Graphiti 方案

## 一、概述

本文档记录将 MiroFish 项目从 Zep Cloud 迁移到 Graphiti (开源版) 的详细方案。

### 1.1 背景

- **当前状态**: 项目使用 Zep Cloud 的 Knowledge Graph API
- **目标**: 替换为开源的 Graphiti，实现本地部署
- **原因**: 减少云服务依赖，降低成本，数据自主可控

### 1.2 替代方案对比

| 方案 | 优点 | 缺点 |
|------|------|------|
| **Graphiti (推荐)** | Zep 官方开源，功能匹配度高 | 需要自建 Neo4j |
| Zep 开源版 | 简单 | 无 Knowledge Graph 功能 |
| Neo4j + 自建 | 完全可控 | 工作量大 |

---

## 二、当前 Zep Cloud 使用分析

### 2.1 涉及的配置文件

| 文件 | 用途 |
|------|------|
| `backend/app/config.py` | ZEP_API_KEY 配置 |
| `.env.example` | 环境变量示例 |
| `README.md` / `README-EN.md` | 文档 |

### 2.2 涉及的代码文件

#### 后端文件

| 文件 | 主要功能 |
|------|---------|
| `app/services/graph_builder.py` | 图谱创建、添加内容、设置本体、删除 |
| `app/services/zep_graph_memory_updater.py` | 批量添加活动到图谱 |
| `app/services/zep_entity_reader.py` | 获取节点、边、实体关系 |
| `app/services/zep_tools.py` | 图谱搜索 |
| `app/services/oasis_profile_generator.py` | 图谱搜索 |
| `app/utils/zep_paging.py` | 分页获取节点和边 |
| `app/services/ontology_generator.py` | 本体生成（动态类） |

#### 前端文件

| 文件 | 内容 | 改动类型 |
|------|------|---------|
| `frontend/src/views/Process.vue` | 显示 "调用 Zep API 构建知识图谱" 文字 | 文本修改 |
| `frontend/src/components/Step1GraphBuild.vue` | 显示 "调用 Zep 构建知识图谱" 描述 | 文本修改 |
| `frontend/src/components/Step2EnvSetup.vue` | 日志显示 "从Zep图谱读取到 X 个实体" | 文本修改 |
| `frontend/src/components/GraphPanel.vue` | 图谱可视化渲染组件 | **无需改动** |
| `frontend/src/api/graph.js` | 图谱 API 调用 | **无需改动** |

> ⚠️ **注意**:
> - 前端仅涉及显示给用户的文本内容，不涉及数据源逻辑
> - **GraphPanel.vue 无需改动** - 它只接收后端返回的数据并使用 D3.js 渲染，不关心数据来自 Zep Cloud 还是 Graphiti
> - 后端需保证返回给前端的数据格式兼容

### 2.3 使用的 API 映射

| Zep Cloud API | Graphiti 对应 | 说明 |
|---------------|--------------|------|
| `client.graph.create()` | `Graphiti` 实例 | 创建图数据库连接 |
| `client.graph.add()` | `graphiti.add_episode()` | 添加内容 |
| `client.graph.add_batch()` | `graphiti.add_episode()` 循环 | 批量添加 |
| `client.graph.set_ontology()` | 自定义 Pydantic 模型 | 设置实体类型 |
| `client.graph.episode.get()` | `graphiti.get_episodes()` | 获取 episode |
| `client.graph.delete()` | `graphiti.delete_episode()` | 删除 |
| `client.graph.search()` | `graphiti.search()` | 搜索 |
| `client.graph.node.get_by_graph_id()` | Neo4j 查询 | 获取节点 |
| `client.graph.edge.get_by_graph_id()` | Neo4j 查询 | 获取边 |
| `client.graph.node.get()` | `graphiti.get_nodes()` | 获取节点 |
| `client.graph.node.get_entity_edges()` | Neo4j 查询 | 获取实体边 |

---

## 三、迁移步骤

### 3.1 第一步：环境准备

#### 3.1.1 部署 Neo4j

**方式一：Docker 部署（推荐）**
```bash
# 创建目录
mkdir -p ~/neo4j/data ~/neo4j/logs

# 启动 Neo4j 容器
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -v ~/neo4j/data:/data \
  -v ~/neo4j/logs:/logs \
  -e NEO4J_AUTH=neo4j/your_password \
  neo4j:5.26
```

**方式二：Neo4j Desktop**
```bash
# 下载安装 Neo4j Desktop
# https://neo4j.com/download/
# 创建本地数据库，设置密码
```

#### 3.1.2 安装 Graphiti

```bash
cd /Users/hmj/Desktop/project/MiroFish/backend

# 添加依赖
pip install graphiti-core neo4j

# 或使用 poetry
poetry add graphiti-core neo4j
```

#### 3.1.3 更新 .env 配置

```bash
# 新增配置
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
OPENAI_API_KEY=your_openai_key

# 保留（可选，兼容旧代码）
# ZEP_API_KEY=xxx  # 可以删除或保留为空
```

---

### 3.2 第二步：代码改造

#### 3.2.1 新增 Graphiti 客户端封装

创建 `backend/app/services/graphiti_client.py`:

```python
"""
Graphiti 客户端封装
替代 Zep Cloud 的 graph API
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from graphiti_core import Graphiti
from graphiti_core.nodes import Episode, EpisodeType
from pydantic import BaseModel

from ..config import Config


class GraphitiClient:
    """Graphiti 客户端封装类"""

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.uri = uri or Config.NEO4J_URI
        self.user = user or Config.NEO4J_USER
        self.password = password or Config.NEO4J_PASSWORD

        if not all([self.uri, self.user, self.password]):
            raise ValueError("Neo4j 配置不完整")

        self.client = Graphiti(
            uri=self.uri,
            user=self.user,
            password=self.password,
        )

    async def add_episode(
        self,
        name: str,
        text: str,
        episode_type: str = "text",
        groups: Optional[List[str]] = None,
    ) -> Episode:
        """添加 Episode 到图谱"""
        episode = Episode(
            name=name,
            episode_type=EpisodeType.TEXT,
            body=text,
            timestamp=datetime.now(timezone.utc),
            groups=groups or [],
        )
        result = await self.client.add_episode(episode)
        return result

    async def search(
        self,
        query: str,
        groups: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """搜索图谱"""
        results = await self.client.search(
            query=query,
            groups=groups,
            limit=limit,
        )
        return [r.model_dump() for r in results]

    async def get_episodes(
        self,
        group: Optional[str] = None,
        limit: int = 100,
    ) -> List[Episode]:
        """获取 Episodes"""
        return await self.client.get_episodes(
            group=group,
            limit=limit,
        )

    async def delete_episode(self, episode_name: str) -> bool:
        """删除 Episode"""
        await self.client.delete_episode(episode_name)
        return True

    # ========== 兼容方法 ==========

    async def graph_create(self, graph_name: str, config: Optional[Dict] = None):
        """兼容方法：创建图（Graphiti 不需要预先创建图）"""
        # Graphiti 使用 group 来区分不同的图
        return {"name": graph_name, "status": "ok"}

    async def graph_add(self, graph_id: str, type: str, data: str, **kwargs):
        """兼容方法：添加内容"""
        return await self.add_episode(
            name=f"{graph_id}_{datetime.now().timestamp()}",
            text=data,
        )

    async def graph_add_batch(self, graph_id: str, items: List[Dict]):
        """兼容方法：批量添加"""
        results = []
        for item in items:
            result = await self.add_episode(
                name=f"{graph_id}_{datetime.now().timestamp()}",
                text=item.get("data", ""),
            )
            results.append(result)
        return results

    async def graph_delete(self, graph_id: str):
        """兼容方法：删除图"""
        # 删除该 group 下的所有 episodes
        episodes = await self.get_episodes(group=graph_id)
        for ep in episodes:
            await self.delete_episode(ep.name)
        return True
```

#### 3.2.2 修改 config.py

```python
# backend/app/config.py 新增

class Config:
    # ... 现有配置 ...

    # Neo4j / Graphiti 配置
    NEO4J_URI = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USER = os.environ.get('NEO4J_USER', 'neo4j')
    NEO4J_PASSWORD = os.environ.get('NEO4J_PASSWORD')

    @classmethod
    def validate(cls):
        errors = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY 未配置")
        # 替换 ZEP_API_KEY 检查为 NEO4J 配置
        if not cls.NEO4J_PASSWORD:
            errors.append("NEO4J_PASSWORD 未配置")
        return errors
```

#### 3.2.3 修改 graph_builder.py

主要改动：
1. 导入替换
2. 初始化客户端替换
3. API 调用替换

详细改动见下方 diff 说明。

#### 3.2.4 修改其他服务文件

| 文件 | 改动说明 |
|------|---------|
| `zep_graph_memory_updater.py` | 替换客户端初始化，替换 add 调用 |
| `zep_entity_reader.py` | 替换客户端，使用 Neo4j 直接查询 |
| `zep_tools.py` | 替换 search 调用 |
| `oasis_profile_generator.py` | 替换 search 调用 |
| `zep_paging.py` | 替换分页逻辑，使用 Neo4j 游标 |
| `ontology_generator.py` | 保留，Pydantic 模型仍可用 |

---

### 3.3 第三步：依赖调整

#### 3.3.1 pyproject.toml / requirements.txt

```toml
# 删除
# zep-cloud

# 添加
graphiti-core = "^0.5.0"
neo4j = "^5.26"
```

#### 3.3.2 uv 操作

```bash
cd backend
uv lock
uv sync
```

---

### 3.4 第四步：测试验证

#### 3.4.1 单元测试

```python
# tests/test_graphiti_client.py

import pytest
from app.services.graphiti_client import GraphitiClient

@pytest.fixture
def client():
    return GraphitiClient()

@pytest.mark.asyncio
async def test_add_episode(client):
    result = await client.add_episode(
        name="test_episode",
        text="这是一条测试数据"
    )
    assert result is not None

@pytest.mark.asyncio
async def test_search(client):
    results = await client.search("测试")
    assert isinstance(results, list)
```

#### 3.4.2 集成测试

1. 启动 Neo4j
2. 启动后端服务
3. 调用图谱创建 API
4. 验证数据添加和搜索

---

## 四、API 对照表

### 4.1 核心功能映射

```
┌─────────────────────────────────────────────────────────────────┐
│                      Zep Cloud → Graphiti                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  client = Zep(api_key=xxx)                                      │
│       ↓                                                          │
│  client = GraphitiClient()                                       │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  # 图谱创建                                                      │
│  client.graph.create(name="xxx")                                │
│       ↓                                                          │
│  # Graphiti 不需要预创建，通过 group 参数区分                    │
│  client.graph_create("xxx")  # 兼容方法                          │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  # 添加内容                                                      │
│  client.graph.add(graph_id="x", type="text", data="y")         │
│       ↓                                                          │
│  await client.add_episode(name="x", text="y")                  │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  # 批量添加                                                     │
│  client.graph.add_batch(graph_id="x", items=[...])             │
│       ↓                                                          │
│  await client.graph_add_batch("x", [...])                       │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  # 搜索                                                         │
│  client.graph.search(graph_id="x", query="y")                   │
│       ↓                                                          │
│  await client.search(query="y", groups=["x"])                   │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  # 获取节点                                                     │
│  client.graph.node.get_by_graph_id(graph_id="x")               │
│       ↓                                                          │
│  # 通过 Neo4j 直接查询 Cypher                                    │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  # 删除图谱                                                     │
│  client.graph.delete(graph_id="x")                              │
│       ↓                                                          │
│  await client.graph_delete("x")                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 数据模型映射

```python
# Zep Cloud
from zep_cloud import EpisodeData
episode = EpisodeData(data="文本", type="text")

# Graphiti
from graphiti_core.nodes import Episode, EpisodeType
episode = Episode(
    name="episode_1",
    episode_type=EpisodeType.TEXT,
    body="文本",
    timestamp=datetime.now(timezone.utc)
)
```

### 4.3 前端数据格式兼容性（重要）

迁移的关键是**保持后端返回给前端的数据格式不变**。前端 `GraphPanel.vue` 期望的数据格式：

#### Nodes 格式（前端期望）

```javascript
{
  "uuid": "xxx",           // 节点唯一ID
  "name": "张三",          // 节点名称
  "labels": ["Person"],    // 实体类型数组
  "summary": "...",        // 摘要
  "attributes": {},        // 其他属性
  "created_at": "2024-01-01T00:00:00"  // 创建时间
}
```

#### Edges 格式（前端期望）

```javascript
{
  "uuid": "xxx",                    // 边唯一ID
  "name": "朋友",                    // 关系名称
  "fact": "...",                    // 事实描述
  "fact_type": "FRIEND",            // 关系类型
  "source_node_uuid": "xxx",        // 源节点ID
  "target_node_uuid": "yyy",        // 目标节点ID
  "source_node_name": "张三",        // 源节点名称
  "target_node_name": "李四",        // 目标节点名称
  "attributes": {},                 // 其他属性
  "created_at": "2024-01-01T00:00:00",
  "valid_at": "2024-01-01T00:00:00",
  "invalid_at": null,
  "expired_at": null,
  "episodes": ["ep1", "ep2"]        // 关联的 episodes
}
```

#### 后端需要修改的文件

| 文件 | 职责 |
|------|------|
| `app/utils/zep_paging.py` | 从 Neo4j 获取节点和边数据 |
| `app/services/graph_builder.py` | 转换数据为前端期望格式 |

> ⚠️ **重要**: 迁移时，后端必须将从 Graphiti/Neo4j 获取的数据转换为上述格式返回给前端，这样前端 `GraphPanel.vue` 组件**无需任何改动**。

---

## 五、风险与注意事项

### 5.1 主要风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Neo4j 性能 | 大规模数据查询慢 | 优化索引，使用 APOC |
| API 差异 | 部分功能不完全匹配 | 使用兼容层封装 |
| 迁移中断 | 服务暂时不可用 | 灰度发布 |

### 5.2 注意事项

1. **数据迁移**: 旧图谱数据需要导出后重新导入
2. **同步问题**: Graphiti 是异步 API，需要使用 async/await
3. **嵌入模型**: 需要配置 OpenAI API Key 用于向量嵌入
4. **版本兼容**: 确认 Neo4j 版本与 Graphiti 兼容

---

## 六、回滚方案

如需回滚到 Zep Cloud：

1. 恢复 `.env` 中的 `ZEP_API_KEY`
2. 恢复代码中对 `zep_cloud` 的引用
3. 移除 `graphiti-core` 依赖

---

## 六、前端改造（如需）

### 6.1 需要修改的文本

将以下文件中的 "Zep" 文本更新为 "Graphiti" 或 "知识图谱"：

#### Step1GraphBuild.vue (第125行)
```vue
<!-- 修改前 -->
基于生成的本体，将文档自动分块后调用 Zep 构建知识图谱，提取实体和关系，并形成时序记忆与社区摘要

<!-- 修改后 -->
基于生成的本体，将文档自动分块后调用 Graphiti 构建知识图谱，提取实体和关系，并形成时序记忆与社区摘要
```

#### Process.vue (第320行)
```vue
<!-- 修改前 -->
基于生成的本体，将文档分块后调用 Zep API 构建知识图谱，提取实体和关系

<!-- 修改后 -->
基于生成的本体，将文档分块后调用 Graphiti 构建知识图谱，提取实体和关系
```

#### Step2EnvSetup.vue (第803行)
```javascript
// 修改前
addLog(`从Zep图谱读取到 ${res.data.expected_entities_count} 个实体`)

// 修改后
addLog(`从知识图谱读取到 ${res.data.expected_entities_count} 个实体`)
```

> 注意: 前端改动仅为展示文本，不影响功能，可选择性修改。

---

## 六、双模式支持设计（推荐）

为了实现平滑迁移，建议采用**配置驱动 + 适配器模式**，同时支持 Zep Cloud 和 Graphiti 两种模式。

### 6.1 设计架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        应用层 (Services)                                 │
├─────────────────────────────────────────────────────────────────────────┤
│  graph_builder.py, zep_tools.py, oasis_profile_generator.py           │
│         │                    │                    │                     │
│         ▼                    ▼                    ▼                     │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              KnowledgeGraphAdapter (抽象适配器)                  │   │
│  │  ┌─────────────────────────────────────────────────────────┐    │   │
│  │  │  def add_episode()                                      │    │   │
│  │  │  def search()                                           │    │   │
│  │  │  def get_nodes()                                        │    │   │
│  │  │  def get_edges()                                        │    │   │
│  │  │  def delete()                                           │    │   │
│  │  └─────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│         ▲                                                        ▲       │
│         │                                                        │       │
│    ┌────┴────┐                                             ┌────┴────┐  │
│    │         │                                             │         │  │
│    ▼         ▼                                             ▼         ▼  │
│ ┌──────────┐                                        ┌──────────┐       │
│ │ZepCloud  │                                        │Graphiti  │       │
│ │Adapter   │                                        │Adapter   │       │
│ └──────────┘                                        └──────────┘       │
│    (当前)                                              (新增)           │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.2 配置项

```bash
# .env 文件

# 模式选择: "cloud" 或 "local"
KNOWLEDGE_GRAPH_MODE=cloud  # 默认使用 Zep Cloud

# Zep Cloud 配置
ZEP_API_KEY=your_zep_api_key

# Graphiti / Neo4j 配置
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
OPENAI_API_KEY=your_openai_key  # 用于嵌入向量
```

### 6.3 核心实现

#### 6.3.1 适配器基类

```python
# backend/app/services/kg_adapter.py

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class KnowledgeGraphAdapter(ABC):
    """知识图谱适配器抽象基类"""

    @abstractmethod
    def add_episode(self, graph_id: str, text: str, **kwargs) -> Any:
        """添加内容"""
        pass

    @abstractmethod
    def add_episodes_batch(self, graph_id: str, texts: List[str]) -> List[Any]:
        """批量添加内容"""
        pass

    @abstractmethod
    def search(self, graph_id: str, query: str, limit: int = 10) -> List[Dict]:
        """搜索"""
        pass

    @abstractmethod
    def get_nodes(self, graph_id: str, limit: int = 100, cursor: str = None) -> List[Dict]:
        """获取节点"""
        pass

    @abstractmethod
    def get_edges(self, graph_id: str, limit: int = 100, cursor: str = None) -> List[Dict]:
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
    def create_graph(self, graph_id: str, name: str = None) -> bool:
        """创建图谱"""
        pass
```

#### 6.3.2 Zep Cloud 适配器（封装现有逻辑）

```python
# backend/app/services/kg_adapter.py 新增

class ZepCloudAdapter(KnowledgeGraphAdapter):
    """Zep Cloud 适配器 - 封装现有逻辑"""

    def __init__(self, api_key: str = None):
        from zep_cloud.client import Zep
        self.api_key = api_key or Config.ZEP_API_KEY
        self.client = Zep(api_key=self.api_key)

    def add_episode(self, graph_id: str, text: str, **kwargs):
        self.client.graph.add(graph_id=graph_id, type="text", data=text)

    def add_episodes_batch(self, graph_id: str, texts: List[str]):
        items = [{"data": t, "type": "text"} for t in texts]
        self.client.graph.add_batch(graph_id=graph_id, items=items)

    def search(self, graph_id: str, query: str, limit: int = 10):
        result = self.client.graph.search(graph_id=graph_id, query=query, limit=limit)
        return [r.model_dump() for r in result.results] if hasattr(result, 'results') else []

    def get_nodes(self, graph_id: str, limit: int = 100, cursor: str = None):
        kwargs = {"limit": limit}
        if cursor:
            kwargs["uuid_cursor"] = cursor
        nodes = self.client.graph.node.get_by_graph_id(graph_id=graph_id, **kwargs)
        return [self._node_to_dict(n) for n in nodes]

    def get_edges(self, graph_id: str, limit: int = 100, cursor: str = None):
        kwargs = {"limit": limit}
        if cursor:
            kwargs["uuid_cursor"] = cursor
        edges = self.client.graph.edge.get_by_graph_id(graph_id=graph_id, **kwargs)
        return [self._edge_to_dict(e) for e in edges]

    def delete(self, graph_id: str):
        self.client.graph.delete(graph_id=graph_id)

    def set_ontology(self, graph_id: str, ontology: Dict):
        self.client.graph.set_ontology(graph_id=graph_id, ontology=ontology)

    def create_graph(self, graph_id: str, name: str = None):
        self.client.graph.create(name=name or graph_id)

    def _node_to_dict(self, node) -> Dict:
        return {
            "uuid_": getattr(node, 'uuid_', None),
            "name": getattr(node, 'name', ''),
            "labels": getattr(node, 'labels', []),
            "summary": getattr(node, 'summary', ''),
            "attributes": getattr(node, 'attributes', {}),
            "created_at": str(getattr(node, 'created_at', '')),
        }

    def _edge_to_dict(self, edge) -> Dict:
        return {
            "uuid_": getattr(edge, 'uuid_', None),
            "name": getattr(edge, 'name', ''),
            "fact": getattr(edge, 'fact', ''),
            "fact_type": getattr(edge, 'fact_type', ''),
            "source_node_uuid": getattr(edge, 'source_node_uuid', ''),
            "target_node_uuid": getattr(edge, 'target_node_uuid', ''),
        }
```

#### 6.3.3 Graphiti 适配器

```python
# backend/app/services/kg_adapter.py 新增

class GraphitiAdapter(KnowledgeGraphAdapter):
    """Graphiti 适配器"""

    def __init__(self):
        from graphiti_core import Graphiti
        from ..config import Config

        self.client = Graphiti(
            uri=Config.NEO4J_URI,
            user=Config.NEO4J_USER,
            password=Config.NEO4J_PASSWORD,
        )
        self._graph_id_to_group = {}  # graph_id -> group 映射

    def add_episode(self, graph_id: str, text: str, **kwargs):
        group = self._get_group(graph_id)
        from graphiti_core.nodes import Episode, EpisodeType
        from datetime import datetime, timezone

        episode = Episode(
            name=f"{graph_id}_{datetime.now().timestamp()}",
            episode_type=EpisodeType.TEXT,
            body=text,
            timestamp=datetime.now(timezone.utc),
            groups=[group],
        )
        return self.client.add_episode(episode)

    def add_episodes_batch(self, graph_id: str, texts: List[str]):
        results = []
        for text in texts:
            result = self.add_episode(graph_id, text)
            results.append(result)
        return results

    def search(self, graph_id: str, query: str, limit: int = 10):
        group = self._get_group(graph_id)
        results = self.client.search(query=query, groups=[group], limit=limit)
        return [self._result_to_dict(r) for r in results]

    def get_nodes(self, graph_id: str, limit: int = 100, cursor: str = None):
        # Graphiti 使用 episodes + entities 结构
        # 需要从 Neo4j 直接查询实体节点
        return self._query_entities(graph_id, limit, cursor)

    def get_edges(self, graph_id: str, limit: int = 100, cursor: str = None):
        return self._query_edges(graph_id, limit, cursor)

    def delete(self, graph_id: str):
        # 删除该 group 下的所有数据
        # 需要实现删除逻辑
        pass

    def set_ontology(self, graph_id: str, ontology: Dict):
        # Graphiti 通过 Pydantic 模型定义实体类型
        # 需要动态创建实体类
        pass

    def create_graph(self, graph_id: str, name: str = None):
        # Graphiti 不需要预创建图，通过 group 参数区分
        self._graph_id_to_group[graph_id] = graph_id

    def _get_group(self, graph_id: str) -> str:
        return self._graph_id_to_group.get(graph_id, graph_id)

    def _result_to_dict(self, result) -> Dict:
        return result.model_dump() if hasattr(result, 'model_dump') else {}

    def _query_entities(self, graph_id: str, limit: int, cursor: str) -> List[Dict]:
        # 通过 Neo4j 驱动直接查询
        from neo4j import GraphDatabase
        from ..config import Config

        driver = GraphDatabase.driver(
            Config.NEO4J_URI,
            auth=(Config.NEO4J_USER, Config.NEO4J_PASSWORD)
        )

        with driver.session() as session:
            query = """
            MATCH (e:Entity)
            WHERE e.group = $group
            RETURN e.uuid as uuid, e.name as name, labels(e) as labels,
                   e.summary as summary, e.created_at as created_at
            LIMIT $limit
            """
            result = session.run(query, group=graph_id, limit=limit)
            return [dict(record) for record in result]

    def _query_edges(self, graph_id: str, limit: int, cursor: str) -> List[Dict]:
        # 通过 Neo4j 驱动直接查询边
        pass
```

#### 6.3.4 工厂函数

```python
# backend/app/services/kg_adapter.py 新增

def get_knowledge_graph_adapter() -> KnowledgeGraphAdapter:
    """获取知识图谱适配器实例"""
    from ..config import Config

    mode = Config.KNOWLEDGE_GRAPH_MODE

    if mode == "local":
        return GraphitiAdapter()
    else:
        return ZepCloudAdapter()
```

#### 6.3.5 配置更新

```python
# backend/app/config.py 新增

class Config:
    # ... 现有配置 ...

    # 知识图谱模式: "cloud" (Zep Cloud) 或 "local" (Graphiti)
    KNOWLEDGE_GRAPH_MODE = os.environ.get('KNOWLEDGE_GRAPH_MODE', 'cloud')

    # Graphiti / Neo4j 配置
    NEO4J_URI = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USER = os.environ.get('NEO4J_USER', 'neo4j')
    NEO4J_PASSWORD = os.environ.get('NEO4J_PASSWORD')
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
```

### 6.4 使用方式

```python
# 在服务中使用
from app.services.kg_adapter import get_knowledge_graph_adapter

class GraphBuilderService:
    def __init__(self, api_key: Optional[str] = None):
        # 使用适配器替代直接调用 Zep Cloud
        self.kg = get_knowledge_graph_adapter()
        # 原有逻辑保持不变

    def build_graph(self, ...):
        self.kg.create_graph(graph_id, name)
        self.kg.add_episode(graph_id, text)
        # ...
```

### 6.5 切换流程

```
1. 开发环境测试
   KNOWLEDGE_GRAPH_MODE=local
   → 使用本地 Graphiti + Neo4j

2. 生产环境并行
   KNOWLEDGE_GRAPH_MODE=cloud
   → 保持 Zep Cloud

3. 迁移完成
   KNOWLEDGE_GRAPH_MODE=local
   → 切换到 Graphiti
```

---

## 七、执行检查清单

- [ ] 1. 部署 Neo4j
- [ ] 2. 安装 graphiti-core 依赖
- [ ] 3. 更新 .env 配置
- [ ] 4. 修改 config.py
- [ ] 5. 创建 graphiti_client.py
- [ ] 6. 修改 graph_builder.py
- [ ] 7. 修改 zep_graph_memory_updater.py
- [ ] 8. 修改 zep_entity_reader.py
- [ ] 9. 修改 zep_tools.py
- [ ] 10. 修改 oasis_profile_generator.py
- [ ] 11. 修改 zep_paging.py
- [ ] 12. 更新 README 文档
- [ ] 13. 修改前端显示文本（可选）
- [ ] 14. 移除 zep_cloud 依赖
- [ ] 15. 测试验证
- [ ] 16. 部署上线

---

## 八、相关资源

- **Graphiti GitHub**: https://github.com/getzep/graphiti
- **Graphiti 文档**: https://getzep.github.io/graphiti/
- **Neo4j 文档**: https://neo4j.com/docs/
- **graphiti-core PyPI**: https://pypi.org/project/graphiti-core/

---

*文档创建时间: 2026-03-10*
*最后更新: 2026-03-10*
