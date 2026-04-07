"""
配置管理
统一从项目根目录的 .env 文件加载配置
"""

import os
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
# 路径: MiroFish/.env (相对于 backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # 如果根目录没有 .env，尝试加载环境变量（用于生产环境）
    load_dotenv(override=True)


class Config:
    """Flask配置类"""
    
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # JSON配置 - 禁用ASCII转义，让中文直接显示（而不是 \uXXXX 格式）
    JSON_AS_ASCII = False
    
    # LLM配置（统一使用OpenAI格式）
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')
    LLM_MAX_TOKENS = int(os.environ.get('LLM_MAX_TOKENS', '4096'))

    # 嵌入模型配置（用于 Graphiti local 模式，可独立配置）
    EMBEDDING_API_KEY = os.environ.get('EMBEDDING_API_KEY')  # 可选，默认使用 LLM_API_KEY
    EMBEDDING_BASE_URL = os.environ.get('EMBEDDING_BASE_URL')  # 可选，默认使用 LLM_BASE_URL
    EMBEDDING_MODEL = os.environ.get('EMBEDDING_MODEL', 'text-embedding-3-small')
    EMBEDDING_DIM = int(os.environ.get('EMBEDDING_DIM', '1536'))
    EMBEDDING_BATCH_SIZE = int(os.environ.get('EMBEDDING_BATCH_SIZE', '5'))  # 批处理大小，默认5

    # 知识图谱模式配置
    # cloud: 使用 Zep Cloud (默认)
    # local: 使用 Graphiti + Neo4j (本地部署)
    KNOWLEDGE_GRAPH_MODE = os.environ.get('KNOWLEDGE_GRAPH_MODE', 'cloud')

    # Zep Cloud 配置 (KNOWLEDGE_GRAPH_MODE=cloud 时需要)
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')

    # Graphiti / Neo4j 配置 (KNOWLEDGE_GRAPH_MODE=local 时需要)
    NEO4J_URI = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USER = os.environ.get('NEO4J_USER', 'neo4j')
    NEO4J_PASSWORD = os.environ.get('NEO4J_PASSWORD')
    # OpenAI API 用于嵌入向量 (Graphiti 模式需要)
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    
    # 文件上传配置
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}
    
    # 文本处理配置
    DEFAULT_CHUNK_SIZE = 500  # 默认切块大小
    DEFAULT_CHUNK_OVERLAP = 50  # 默认重叠大小
    
    # OASIS模拟配置
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')
    
    # OASIS平台可用动作配置
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]
    
    # Report Agent配置
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))

    # LLM 超时配置（秒）
    LLM_TIMEOUT = int(os.environ.get('LLM_TIMEOUT', '120'))
    
    @classmethod
    def validate(cls):
        """验证必要配置"""
        errors = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY 未配置")

        # 根据模式验证对应的配置
        if cls.KNOWLEDGE_GRAPH_MODE == 'cloud':
            if not cls.ZEP_API_KEY:
                errors.append("ZEP_API_KEY 未配置 (当前模式: cloud)")
        elif cls.KNOWLEDGE_GRAPH_MODE == 'local':
            if not cls.NEO4J_PASSWORD:
                errors.append("NEO4J_PASSWORD 未配置 (当前模式: local)")
            if not cls.LLM_API_KEY and not cls.OPENAI_API_KEY:
                errors.append("LLM_API_KEY 或 OPENAI_API_KEY 未配置 (当前模式: local，用于嵌入向量)")
        else:
            errors.append(f"未知的 KNOWLEDGE_GRAPH_MODE: {cls.KNOWLEDGE_GRAPH_MODE}")

        return errors

