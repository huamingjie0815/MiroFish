"""
API路由模块
"""

from flask import Blueprint

from .response import ApiResponse, api_exception_handler

graph_bp = Blueprint('graph', __name__)
simulation_bp = Blueprint('simulation', __name__)
report_bp = Blueprint('report', __name__)

# 导出给其他模块使用
__all__ = ['graph_bp', 'simulation_bp', 'report_bp', 'ApiResponse', 'api_exception_handler']

from . import graph  # noqa: E402, F401
from . import simulation  # noqa: E402, F401
from . import report  # noqa: E402, F401

