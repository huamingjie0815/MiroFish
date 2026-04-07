# Knowledge Graph Dual-Mode Guide

MiroFish supports two knowledge graph modes: **Cloud Mode** and **Local Mode**. Choose based on your requirements.

## Mode Overview

| Mode | Deployment | Use Case |
|------|------------|----------|
| Cloud | Zep Cloud API | Quick setup, no local deployment |
| Local | Graphiti + Neo4j | Data privacy, full control |

## Quick Start

### 1. Choose Mode

Set `KNOWLEDGE_GRAPH_MODE` in your `.env` file:

```env
# Cloud Mode (default)
KNOWLEDGE_GRAPH_MODE=cloud

# Local Mode
KNOWLEDGE_GRAPH_MODE=local
```

### 2. Configure Corresponding Parameters

#### Cloud Mode Configuration

```env
KNOWLEDGE_GRAPH_MODE=cloud
ZEP_API_KEY=your_zep_api_key_here
```

**Get Zep API Key:**
1. Visit [Zep Cloud](https://app.getzep.com/)
2. Register and create a project
3. Find API Key in project settings
4. Free tier is sufficient for basic usage

#### Local Mode Configuration

```env
KNOWLEDGE_GRAPH_MODE=local

# Neo4j Database Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password

# Embedding API (OpenAI-compatible)
OPENAI_API_KEY=your_openai_key_here
# Or use other OpenAI-compatible services:
# OPENAI_BASE_URL=https://your-custom-api.com/v1
```

**Local Mode Prerequisites:**

1. **Install Neo4j**
   ```bash
   # macOS (Homebrew)
   brew install neo4j
   brew services start neo4j

   # Or use Docker
   docker run -d --name neo4j \
     -p 7474:7474 -p 7687:7687 \
     -e NEO4J_AUTH=neo4j/password \
     neo4j
   ```

2. **Configure Embedding API**
   - Supports OpenAI, Alibaba Cloud Bailian, Cohere, Ollama, LM Studio, etc.
   - Ensure API is accessible

## Switching Modes

Modify `KNOWLEDGE_GRAPH_MODE` in `.env` and restart the service.

```bash
# Restart backend
cd backend
python app.py
```

## Configuration Reference

### Common Knowledge Graph Config

| Parameter | Description | Default |
|-----------|-------------|---------|
| `KNOWLEDGE_GRAPH_MODE` | Mode: `cloud` or `local` | `cloud` |

### Cloud Mode Parameters

| Parameter | Description |
|-----------|-------------|
| `ZEP_API_KEY` | Zep Cloud API Key |

### Local Mode Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `NEO4J_URI` | Neo4j connection URL | `bolt://localhost:7687` |
| `NEO4J_USER` | Neo4j username | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j password | - |
| `OPENAI_API_KEY` | Embedding API Key | uses `LLM_API_KEY` |

### Embedding Model Config (Local Mode)

| Parameter | Description | Default |
|-----------|-------------|---------|
| `EMBEDDING_API_KEY` | Embedding API Key | uses `LLM_API_KEY` |
| `EMBEDDING_BASE_URL` | Embedding API URL | uses `LLM_BASE_URL` |
| `EMBEDDING_MODEL` | Embedding model name | `text-embedding-3-small` |
| `EMBEDDING_DIM` | Embedding vector dimension | `1536` |
| `EMBEDDING_BATCH_SIZE` | Batch size | `5` |

## FAQ

### Q1: How to check which mode is active?

Check the value of `KNOWLEDGE_GRAPH_MODE` in your `.env` file.

### Q2: Local mode fails to start?

1. Confirm Neo4j is running: `brew services list` or `docker ps`
2. Check `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` are correct
3. Verify embedding API is accessible

### Q3: Cloud mode returns empty results?

1. Confirm `ZEP_API_KEY` is correctly configured
2. Check network connectivity
3. Verify Zep Cloud account status is active

### Q4: Can I switch modes in the same project?

Yes. Change `KNOWLEDGE_GRAPH_MODE` and restart. Note:
- Cloud and Local data are not shared
- You need to re-import data after switching

## Related Documentation

- [Zep Cloud Documentation](https://docs.getzep.com/)
- [Graphiti GitHub](https://github.com/getzep/graphiti)
- [Neo4j Documentation](https://neo4j.com/docs/)
