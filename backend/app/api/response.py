"""
统一 API 响应格式
"""

from flask import jsonify
from functools import wraps
import traceback

from ..config import Config


class ApiResponse:
    """统一 API 响应格式"""

    @staticmethod
    def success(data=None, message: str = None, **kwargs):
        """成功响应"""
        response = {
            "success": True,
            "data": data
        }
        if message:
            response["message"] = message
        response.update(kwargs)
        return jsonify(response), 200

    @staticmethod
    def error(message: str, code: int = 500, error: str = None, **kwargs):
        """错误响应"""
        response = {
            "success": False,
            "error": message
        }
        if error and not Config.DEBUG:
            # 生产环境不暴露详细信息
            response["error"] = "服务器内部错误"
        elif error:
            response["detail"] = error
        response.update(kwargs)
        return jsonify(response), code

    @staticmethod
    def created(data=None, message: str = "创建成功", **kwargs):
        """创建成功响应"""
        response = {
            "success": True,
            "data": data,
            "message": message
        }
        response.update(kwargs)
        return jsonify(response), 201

    @staticmethod
    def not_found(message: str = "资源未找到", **kwargs):
        """404 响应"""
        response = {
            "success": False,
            "error": message
        }
        response.update(kwargs)
        return jsonify(response), 404

    @staticmethod
    def bad_request(message: str = "请求参数错误", **kwargs):
        """400 响应"""
        response = {
            "success": False,
            "error": message
        }
        response.update(kwargs)
        return jsonify(response), 400

    @staticmethod
    def unauthorized(message: str = "未授权", **kwargs):
        """401 响应"""
        response = {
            "success": False,
            "error": message
        }
        response.update(kwargs)
        return jsonify(response), 401


def api_exception_handler(f):
    """API 异常处理装饰器

    统一处理 API 函数中的异常：
    - 生产环境：只返回简化的错误信息
    - 调试环境：返回详细的错误信息和 traceback
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            return ApiResponse.bad_request(str(e))
        except FileNotFoundError as e:
            return ApiResponse.not_found(str(e))
        except PermissionError as e:
            return ApiResponse.error("权限不足", code=403)
        except Exception as e:
            error_detail = traceback.format_exc()
            return ApiResponse.error(str(e), error=error_detail)
    return decorated_function
