# 知识图谱双模式说明

MiroFish 支持两种知识图谱模式，您可以根据需求选择使用 **Cloud 模式** 或 **Local 模式**。

## 模式简介

| 模式 | 部署方式 | 适用场景 |
|------|----------|----------|
| Cloud | Zep Cloud API | 快速上手、无需本地部署 |
| Local | Graphiti + Neo4j | 数据隐私、完全控制 |

## 快速开始

### 1. 选择模式

在 `.env` 文件中设置 `KNOWLEDGE_GRAPH_MODE`:

```env
# Cloud 模式 (默认)
KNOWLEDGE_GRAPH_MODE=cloud

# Local 模式
KNOWLEDGE_GRAPH_MODE=local
```

### 2. 配置对应参数

#### Cloud 模式配置

```env
KNOWLEDGE_GRAPH_MODE=cloud
ZEP_API_KEY=your_zep_api_key_here
```

**获取 Zep API Key:**
1. 访问 [Zep Cloud](https://app.getzep.com/)
2. 注册账号并创建项目
3. 在项目设置中找到 API Key
4. 每月免费额度即可支撑简单使用

#### Local 模式配置

```env
KNOWLEDGE_GRAPH_MODE=local

# Neo4j 数据库配置
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password

# 嵌入向量 API (支持 OpenAI 兼容 API)
OPENAI_API_KEY=your_openai_key_here
# 或使用其他 OpenAI 兼容服务:
# OPENAI_BASE_URL=https://your-custom-api.com/v1
```

**Local 模式前置要求:**

1. **安装 Neo4j**
   ```bash
   # macOS (Homebrew)
   brew install neo4j
   brew services start neo4j

   # 或使用 Docker
   docker run -d --name neo4j \
     -p 7474:7474 -p 7687:7687 \
     -e NEO4J_AUTH=neo4j/password \
     neo4j
   ```

2. **配置嵌入向量 API**
   - 支持 OpenAI、阿里云百炼、Cohere、Ollama、LM Studio 等
   - 确保 API 可访问

## 切换模式

修改 `.env` 文件中的 `KNOWLEDGE_GRAPH_MODE` 后，重启服务即可生效。

```bash
# 重启后端服务
cd backend
python app.py
```

## 配置参数说明

### 知识图谱通用配置

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `KNOWLEDGE_GRAPH_MODE` | 模式选择: `cloud` 或 `local` | `cloud` |

### Cloud 模式参数

| 参数 | 说明 |
|------|------|
| `ZEP_API_KEY` | Zep Cloud API Key |

### Local 模式参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `NEO4J_URI` | Neo4j 连接地址 | `bolt://localhost:7687` |
| `NEO4J_USER` | Neo4j 用户名 | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j 密码 | - |
| `OPENAI_API_KEY` | 嵌入向量 API Key | 使用 `LLM_API_KEY` |

### 嵌入模型配置 (Local 模式)

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `EMBEDDING_API_KEY` | 嵌入模型 API Key | 使用 `LLM_API_KEY` |
| `EMBEDDING_BASE_URL` | 嵌入模型 API 地址 | 使用 `LLM_BASE_URL` |
| `EMBEDDING_MODEL` | 嵌入模型名称 | `text-embedding-3-small` |
| `EMBEDDING_DIM` | 嵌入向量维度 | `1536` |
| `EMBEDDING_BATCH_SIZE` | 批处理大小 | `5` |

## 常见问题

### Q1: 如何判断当前使用哪种模式?

检查 `.env` 文件中 `KNOWLEDGE_GRAPH_MODE` 的值。

### Q2: Local 模式启动失败?

1. 确认 Neo4j 已启动: `brew services list` 或 `docker ps`
2. 检查 `NEO4J_URI`、`NEO4J_USER`、`NEO4J_PASSWORD` 配置是否正确
3. 确认嵌入向量 API 可访问

### Q3: Cloud 模式返回空结果?

1. 确认 `ZEP_API_KEY` 正确配置
2. 检查网络连接是否正常
3. 确认 Zep Cloud 账户状态正常

### Q4: 可以在同一项目中切换模式吗?

可以。修改 `KNOWLEDGE_GRAPH_MODE` 并重启服务即可。但注意:
- Cloud 和 Local 的数据不互通
- 切换后需要重新导入数据

## 相关文档

- [Zep Cloud 官方文档](https://docs.getzep.com/)
- [Graphiti GitHub](https://github.com/getzep/graphiti)
- [Neo4j 官方文档](https://neo4j.com/docs/)
