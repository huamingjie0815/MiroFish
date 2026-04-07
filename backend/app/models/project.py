"""
项目上下文管理
用于在服务端持久化项目状态，避免前端在接口间传递大量数据
"""

import os
import json
import threading
import uuid
import shutil
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass, field, asdict
from functools import lru_cache
from ..config import Config


class ProjectStatus(str, Enum):
    """项目状态"""
    CREATED = "created"              # 刚创建，文件已上传
    ONTOLOGY_GENERATED = "ontology_generated"  # 本体已生成
    GRAPH_BUILDING = "graph_building"    # 图谱构建中
    GRAPH_COMPLETED = "graph_completed"  # 图谱构建完成
    FAILED = "failed"                # 失败


@dataclass
class Project:
    """项目数据模型"""
    project_id: str
    name: str
    status: ProjectStatus
    created_at: str
    updated_at: str
    
    # 文件信息
    files: List[Dict[str, str]] = field(default_factory=list)  # [{filename, path, size}]
    total_text_length: int = 0
    
    # 本体信息（接口1生成后填充）
    ontology: Optional[Dict[str, Any]] = None
    analysis_summary: Optional[str] = None
    
    # 图谱信息（接口2完成后填充）
    graph_id: Optional[str] = None
    graph_build_task_id: Optional[str] = None
    
    # 配置
    simulation_requirement: Optional[str] = None
    chunk_size: int = 500
    chunk_overlap: int = 50
    
    # 错误信息
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "project_id": self.project_id,
            "name": self.name,
            "status": self.status.value if isinstance(self.status, ProjectStatus) else self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "files": self.files,
            "total_text_length": self.total_text_length,
            "ontology": self.ontology,
            "analysis_summary": self.analysis_summary,
            "graph_id": self.graph_id,
            "graph_build_task_id": self.graph_build_task_id,
            "simulation_requirement": self.simulation_requirement,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "error": self.error
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        """从字典创建"""
        status = data.get('status', 'created')
        if isinstance(status, str):
            status = ProjectStatus(status)
        
        return cls(
            project_id=data['project_id'],
            name=data.get('name', 'Unnamed Project'),
            status=status,
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
            files=data.get('files', []),
            total_text_length=data.get('total_text_length', 0),
            ontology=data.get('ontology'),
            analysis_summary=data.get('analysis_summary'),
            graph_id=data.get('graph_id'),
            graph_build_task_id=data.get('graph_build_task_id'),
            simulation_requirement=data.get('simulation_requirement'),
            chunk_size=data.get('chunk_size', 500),
            chunk_overlap=data.get('chunk_overlap', 50),
            error=data.get('error')
        )


class ProjectManager:
    """项目管理器 - 负责项目的持久化存储和检索"""

    # 项目存储根目录
    PROJECTS_DIR = os.path.join(Config.UPLOAD_FOLDER, 'projects')

    # 内存缓存（项目ID -> Project 对象）
    _project_cache: Dict[str, Project] = {}

    # 线程安全锁
    _cache_lock = threading.Lock()

    # 列表缓存（用于 list_projects）
    _list_cache: Optional[List[Project]] = None
    _list_cache_time: Optional[datetime] = None
    _LIST_CACHE_TTL = 30  # 缓存 30 秒
    
    @classmethod
    def _invalidate_cache(cls):
        """清除列表缓存"""
        cls._list_cache = None
        cls._list_cache_time = None

    @classmethod
    def _ensure_projects_dir(cls):
        """确保项目目录存在"""
        os.makedirs(cls.PROJECTS_DIR, exist_ok=True)
    
    @classmethod
    def _get_project_dir(cls, project_id: str) -> str:
        """获取项目目录路径"""
        return os.path.join(cls.PROJECTS_DIR, project_id)
    
    @classmethod
    def _get_project_meta_path(cls, project_id: str) -> str:
        """获取项目元数据文件路径"""
        return os.path.join(cls._get_project_dir(project_id), 'project.json')
    
    @classmethod
    def _get_project_files_dir(cls, project_id: str) -> str:
        """获取项目文件存储目录"""
        return os.path.join(cls._get_project_dir(project_id), 'files')
    
    @classmethod
    def _get_project_text_path(cls, project_id: str) -> str:
        """获取项目提取文本存储路径"""
        return os.path.join(cls._get_project_dir(project_id), 'extracted_text.txt')
    
    @classmethod
    def create_project(cls, name: str = "Unnamed Project") -> Project:
        """
        创建新项目

        Args:
            name: 项目名称

        Returns:
            新创建的Project对象
        """
        cls._ensure_projects_dir()

        project_id = f"proj_{uuid.uuid4().hex[:12]}"
        now = datetime.now().isoformat()

        project = Project(
            project_id=project_id,
            name=name,
            status=ProjectStatus.CREATED,
            created_at=now,
            updated_at=now
        )

        # 创建项目目录结构
        project_dir = cls._get_project_dir(project_id)
        files_dir = cls._get_project_files_dir(project_id)
        os.makedirs(project_dir, exist_ok=True)
        os.makedirs(files_dir, exist_ok=True)

        # 保存项目元数据
        cls.save_project(project)

        # 清除列表缓存
        cls._invalidate_cache()

        return project
    
    @classmethod
    def save_project(cls, project: Project) -> None:
        """保存项目元数据"""
        project.updated_at = datetime.now().isoformat()
        meta_path = cls._get_project_meta_path(project.project_id)

        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(project.to_dict(), f, ensure_ascii=False, indent=2)

        # 更新缓存
        with cls._cache_lock:
            cls._project_cache[project.project_id] = project
            cls._invalidate_cache()
    
    @classmethod
    def get_project(cls, project_id: str) -> Optional[Project]:
        """
        获取项目

        Args:
            project_id: 项目ID

        Returns:
            Project对象，如果不存在返回None
        """
        # 先从缓存获取
        with cls._cache_lock:
            if project_id in cls._project_cache:
                return cls._project_cache[project_id]

        meta_path = cls._get_project_meta_path(project_id)

        if not os.path.exists(meta_path):
            return None

        with open(meta_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        project = Project.from_dict(data)
        # 存入缓存
        with cls._cache_lock:
            cls._project_cache[project_id] = project
        return project
    
    @classmethod
    def list_projects(cls, limit: int = 50) -> List[Project]:
        """
        列出所有项目

        Args:
            limit: 返回数量限制

        Returns:
            项目列表，按创建时间倒序
        """
        cls._ensure_projects_dir()

        # 检查缓存是否有效
        now = datetime.now()
        with cls._cache_lock:
            if cls._list_cache is not None and cls._list_cache_time is not None:
                cache_age = (now - cls._list_cache_time).total_seconds()
                if cache_age < cls._LIST_CACHE_TTL:
                    return cls._list_cache[:limit]

        # 重新加载列表
        projects = []
        for project_id in os.listdir(cls.PROJECTS_DIR):
            project = cls.get_project(project_id)
            if project:
                projects.append(project)

        # 按创建时间倒序排序
        projects.sort(key=lambda p: p.created_at, reverse=True)

        # 更新缓存
        with cls._cache_lock:
            cls._list_cache = projects
            cls._list_cache_time = now

        return projects[:limit]
    
    @classmethod
    def delete_project(cls, project_id: str) -> bool:
        """
        删除项目及其所有文件

        Args:
            project_id: 项目ID

        Returns:
            是否删除成功
        """
        project_dir = cls._get_project_dir(project_id)

        if not os.path.exists(project_dir):
            return False

        shutil.rmtree(project_dir)

        # 清除缓存
        with cls._cache_lock:
            if project_id in cls._project_cache:
                del cls._project_cache[project_id]
            cls._invalidate_cache()

        return True
    
    @classmethod
    def save_file_to_project(cls, project_id: str, file_storage, original_filename: str) -> Dict[str, str]:
        """
        保存上传的文件到项目目录
        
        Args:
            project_id: 项目ID
            file_storage: Flask的FileStorage对象
            original_filename: 原始文件名
            
        Returns:
            文件信息字典 {filename, path, size}
        """
        files_dir = cls._get_project_files_dir(project_id)
        os.makedirs(files_dir, exist_ok=True)
        
        # 生成安全的文件名
        ext = os.path.splitext(original_filename)[1].lower()
        safe_filename = f"{uuid.uuid4().hex[:8]}{ext}"
        file_path = os.path.join(files_dir, safe_filename)
        
        # 保存文件
        file_storage.save(file_path)
        
        # 获取文件大小
        file_size = os.path.getsize(file_path)
        
        return {
            "original_filename": original_filename,
            "saved_filename": safe_filename,
            "path": file_path,
            "size": file_size
        }
    
    @classmethod
    def save_extracted_text(cls, project_id: str, text: str) -> None:
        """保存提取的文本"""
        text_path = cls._get_project_text_path(project_id)
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(text)
    
    @classmethod
    def get_extracted_text(cls, project_id: str) -> Optional[str]:
        """获取提取的文本"""
        text_path = cls._get_project_text_path(project_id)
        
        if not os.path.exists(text_path):
            return None
        
        with open(text_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    @classmethod
    def get_project_files(cls, project_id: str) -> List[str]:
        """获取项目的所有文件路径"""
        files_dir = cls._get_project_files_dir(project_id)
        
        if not os.path.exists(files_dir):
            return []
        
        return [
            os.path.join(files_dir, f) 
            for f in os.listdir(files_dir) 
            if os.path.isfile(os.path.join(files_dir, f))
        ]

