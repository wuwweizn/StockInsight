"""
FastAPI路由和接口
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Body, Cookie, Depends
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Template
import os
from typing import Optional, Dict, List, Any
import json
import asyncio
from datetime import datetime
from pydantic import BaseModel
import pandas as pd
import io
from app.database import Database
from app.config import Config
from app.statistics import Statistics
from app.data_updater import DataUpdater
from app.data_fetcher import DataFetcher
from app.auth import AuthManager

app = FastAPI(title="StockInsight - 股票洞察分析系统")

# 初始化
db = Database()
config = Config()
statistics = Statistics(db)
updater = DataUpdater(db, config)
auth = AuthManager(db)

# 定期清理过期会话
import threading
def cleanup_sessions_periodically():
    while True:
        import time
        time.sleep(3600)  # 每小时清理一次
        db.cleanup_expired_sessions()

cleanup_thread = threading.Thread(target=cleanup_sessions_periodically, daemon=True)
cleanup_thread.start()

# 进度状态（用于实时返回更新进度）
update_progress = {
    'current': 0,
    'total': 100,
    'message': '',
    'is_running': False
}

# 静态文件
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


def progress_callback(current: int, total: int, message: str = ""):
    """进度回调函数"""
    update_progress['current'] = current
    update_progress['total'] = total
    update_progress['message'] = message


# ========== 认证相关API ==========

@app.post("/api/auth/login")
async def login(data: Dict = Body(...), response: JSONResponse = None):
    """用户登录"""
    try:
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return {"success": False, "message": "用户名和密码不能为空"}
        
        result = auth.login(username, password)
        
        # 创建响应并设置Cookie
        response = JSONResponse({
            "success": True,
            "message": "登录成功",
            "user": result['user']
        })
        response.set_cookie(
            key="session_id",
            value=result['session_id'],
            max_age=86400 * 365,  # 1年
            httponly=True,
            samesite="lax"
        )
        return response
    except HTTPException as e:
        return {"success": False, "message": e.detail}
    except Exception as e:
        return {"success": False, "message": f"登录失败: {str(e)}"}


@app.post("/api/auth/logout")
async def logout(session_id: Optional[str] = Cookie(None)):
    """用户登出"""
    if session_id:
        auth.logout(session_id)
    response = JSONResponse({"success": True, "message": "已登出"})
    response.delete_cookie(key="session_id")
    return response


@app.get("/api/auth/current-user")
async def get_current_user(session_id: Optional[str] = Cookie(None)):
    """获取当前登录用户信息"""
    user = auth.get_current_user(session_id)
    if user:
        return {"success": True, "user": user}
    else:
        return {"success": False, "user": None}


# ========== 用户管理API（仅管理员） ==========

@app.get("/api/users")
async def get_users(session_id: Optional[str] = Cookie(None)):
    """获取所有用户列表（仅管理员）"""
    auth.require_admin(session_id)
    try:
        users = db.get_all_users()
        return {"success": True, "data": users}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/users")
async def create_user(data: Dict = Body(...), session_id: Optional[str] = Cookie(None)):
    """创建用户（仅管理员）"""
    auth.require_admin(session_id)
    try:
        username = data.get('username', '').strip()
        password = data.get('password', '')
        role = data.get('role', 'user')
        valid_until = data.get('valid_until')  # 格式：YYYYMMDDHHMMSS 或 None
        
        if not username or not password:
            return {"success": False, "message": "用户名和密码不能为空"}
        
        if role not in ['admin', 'user']:
            return {"success": False, "message": "角色必须是 admin 或 user"}
        
        user_id = db.create_user(username, password, role, valid_until)
        # 新建用户默认无权限（已在数据库层面实现，这里不需要额外操作）
        return {"success": True, "message": "用户创建成功", "user_id": user_id}
    except ValueError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        return {"success": False, "message": f"创建用户失败: {str(e)}"}


@app.get("/api/users/{user_id}")
async def get_user(user_id: int, session_id: Optional[str] = Cookie(None)):
    """获取单个用户信息（仅管理员）"""
    auth.require_admin(session_id)
    try:
        user = db.get_user_by_id(user_id)
        if not user:
            return {"success": False, "message": "用户不存在"}
        return {"success": True, "data": user}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.put("/api/users/{user_id}")
async def update_user(user_id: int, data: Dict = Body(...), session_id: Optional[str] = Cookie(None)):
    """更新用户信息（仅管理员）"""
    auth.require_admin(session_id)
    try:
        username = data.get('username')
        password = data.get('password')
        role = data.get('role')
        is_active = data.get('is_active')
        valid_until = data.get('valid_until')
        
        if role and role not in ['admin', 'user']:
            return {"success": False, "message": "角色必须是 admin 或 user"}
        
        db.update_user(user_id, username, password, role, is_active, valid_until)
        return {"success": True, "message": "用户信息已更新"}
    except Exception as e:
        return {"success": False, "message": f"更新用户失败: {str(e)}"}


@app.delete("/api/users/{user_id}")
async def delete_user(user_id: int, session_id: Optional[str] = Cookie(None)):
    """删除用户（仅管理员）"""
    auth.require_admin(session_id)
    try:
        # 不能删除自己
        current_user = auth.get_current_user(session_id)
        if current_user and current_user['id'] == user_id:
            return {"success": False, "message": "不能删除自己的账号"}
        
        db.delete_user(user_id)
        return {"success": True, "message": "用户已删除"}
    except Exception as e:
        return {"success": False, "message": f"删除用户失败: {str(e)}"}


# ========== 权限管理API（仅管理员） ==========

@app.get("/api/permissions")
async def get_all_permissions(session_id: Optional[str] = Cookie(None)):
    """获取所有权限列表（仅管理员）"""
    auth.require_admin(session_id)
    from app.permissions import get_all_permissions
    return {"success": True, "data": get_all_permissions()}


@app.get("/api/users/{user_id}/permissions")
async def get_user_permissions(user_id: int, session_id: Optional[str] = Cookie(None)):
    """获取用户权限列表（仅管理员）"""
    auth.require_admin(session_id)
    try:
        permissions = db.get_user_permissions(user_id)
        return {"success": True, "data": permissions}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.put("/api/users/{user_id}/permissions")
async def update_user_permissions(user_id: int, data: Dict = Body(...), session_id: Optional[str] = Cookie(None)):
    """更新用户权限（仅管理员）"""
    auth.require_admin(session_id)
    try:
        permission_codes = data.get('permissions', [])
        db.set_user_permissions(user_id, permission_codes)
        return {"success": True, "message": "权限已更新"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/api/auth/change-password")
async def change_password(data: Dict = Body(...), session_id: Optional[str] = Cookie(None)):
    """修改密码（当前用户）"""
    user = auth.require_auth(session_id)
    try:
        old_password = data.get('old_password', '')
        new_password = data.get('new_password', '')
        
        if not old_password or not new_password:
            return {"success": False, "message": "旧密码和新密码不能为空"}
        
        # 验证旧密码
        user_info = db.get_user_by_id(user['id'])
        if not auth.verify_password(old_password, user_info['password_hash']):
            return {"success": False, "message": "旧密码错误"}
        
        # 更新密码
        db.update_user(user['id'], password=new_password)
        return {"success": True, "message": "密码修改成功"}
    except Exception as e:
        return {"success": False, "message": f"修改密码失败: {str(e)}"}


@app.get("/api/system/config")
async def get_system_config(session_id: Optional[str] = Cookie(None)):
    """获取系统配置（仅管理员）"""
    auth.require_admin(session_id)
    try:
        session_duration = db.get_system_config('session_duration_hours', '24')
        return {"success": True, "data": {"session_duration_hours": int(session_duration)}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/system/config")
async def update_system_config(data: Dict = Body(...), session_id: Optional[str] = Cookie(None)):
    """更新系统配置（仅管理员）"""
    auth.require_admin(session_id)
    try:
        session_duration = data.get('session_duration_hours')
        if session_duration:
            db.set_system_config('session_duration_hours', str(session_duration))
        return {"success": True, "message": "系统配置已更新"}
    except Exception as e:
        return {"success": False, "message": f"更新配置失败: {str(e)}"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """首页"""
    template_path = os.path.join("templates", "index.html")
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            template = Template(f.read())
        return HTMLResponse(content=template.render())
    else:
        return HTMLResponse(content="<h1>模板文件未找到</h1>", status_code=404)


@app.get("/api/stocks")
async def get_stocks():
    """获取股票列表"""
    try:
        stocks_df = db.get_stocks(exclude_delisted=True)
        stocks = stocks_df.to_dict('records')
        return {"success": True, "data": stocks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stocks/search")
async def search_stocks(keyword: str = "", limit: int = 20):
    """搜索股票（根据代码或名称）"""
    try:
        if not keyword or len(keyword) < 1:
            return {"success": True, "data": []}
        
        results = db.search_stocks(keyword, limit=limit)
        return {"success": True, "data": results}
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Error in search_stocks: {error_detail}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stock/{code}")
async def get_stock_info(code: str):
    """获取股票信息"""
    try:
        stock = db.get_stock_by_code(code)
        if stock:
            return {"success": True, "data": stock}
        else:
            raise HTTPException(status_code=404, detail="股票不存在")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/stock/statistics")
async def get_stock_statistics(data: Dict = Body(...), session_id: Optional[str] = Cookie(None)):
    """单只股票月份统计"""
    auth.require_permission(session_id, 'stock_analysis_single')
    try:
        code = data.get('code', '').strip()
        month = int(data.get('month', 1))
        start_year = data.get('start_year')
        end_year = data.get('end_year')
        
        if not code:
            return {"success": False, "message": "股票代码不能为空"}
        
        # 转换年份为整数（如果提供）
        if start_year:
            try:
                start_year = int(start_year)
            except (ValueError, TypeError):
                start_year = None
        
        if end_year:
            try:
                end_year = int(end_year)
            except (ValueError, TypeError):
                end_year = None
        
        stock = db.get_stock_by_code(code)
        if not stock:
            return {"success": False, "message": f"股票代码 {code} 不存在，请先更新数据"}
        
        # 获取数据源（优先使用请求参数，否则使用配置的数据源）
        requested_data_source = data.get('data_source')
        current_data_source = requested_data_source if requested_data_source else config.get('data_source', 'akshare')
        
        result = statistics.calculate_stock_month_statistics(
            stock['ts_code'], month, start_year, end_year, data_source=current_data_source
        )
        result['symbol'] = stock.get('symbol', code)
        result['name'] = stock.get('name', '')
        result['data_source'] = current_data_source
        
        return {"success": True, "data": result}
    except ValueError as e:
        return {"success": False, "message": f"参数错误: {str(e)}"}
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Error in get_stock_statistics: {error_detail}")
        return {"success": False, "message": f"查询失败: {str(e)}"}


@app.post("/api/stock/multi-month-statistics")
async def get_stock_multi_month_statistics(data: Dict = Body(...), session_id: Optional[str] = Cookie(None)):
    """单只股票多月份统计"""
    auth.require_permission(session_id, 'stock_analysis_multi')
    try:
        code = data.get('code', '').strip()
        months = data.get('months', [])
        start_year = data.get('start_year')
        end_year = data.get('end_year')
        
        if not code:
            return {"success": False, "message": "股票代码不能为空"}
        
        # 如果没有指定月份或月份列表为空，默认查询所有月份
        if months is None or (isinstance(months, list) and len(months) == 0):
            months = list(range(1, 13))  # 默认查询所有月份
        
        # 转换年份为整数（如果提供）
        if start_year:
            try:
                start_year = int(start_year)
            except (ValueError, TypeError):
                start_year = None
        
        if end_year:
            try:
                end_year = int(end_year)
            except (ValueError, TypeError):
                end_year = None
        
        stock = db.get_stock_by_code(code)
        if not stock:
            return {"success": False, "message": f"股票代码 {code} 不存在，请先更新数据"}
        
        # 获取数据源（优先使用请求参数，否则使用配置的数据源）
        requested_data_source = data.get('data_source')
        current_data_source = requested_data_source if requested_data_source else config.get('data_source', 'akshare')
        
        # 计算每个月份的统计
        results = []
        for month in months:
            stat = statistics.calculate_stock_month_statistics(
                stock['ts_code'], month, start_year, end_year, data_source=current_data_source
            )
            if stat['total_count'] > 0:  # 只包含有数据的月份
                stat['month'] = month
                stat['symbol'] = stock.get('symbol', code)
                stat['name'] = stock.get('name', '')
                stat['data_source'] = current_data_source
                results.append(stat)
        
        # 按月份排序
        results.sort(key=lambda x: x['month'])
        
        return {"success": True, "data": results}
    except ValueError as e:
        return {"success": False, "message": f"参数错误: {str(e)}"}
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Error in get_stock_multi_month_statistics: {error_detail}")
        return {"success": False, "message": f"查询失败: {str(e)}"}


@app.post("/api/month/filter")
async def get_month_filter_statistics(data: Dict = Body(...), session_id: Optional[str] = Cookie(None)):
    """月份筛选统计（前20支）"""
    auth.require_permission(session_id, 'month_filter')
    try:
        month = int(data.get('month', 1))
        start_year = int(data.get('start_year', 2000))
        end_year = int(data.get('end_year', datetime.now().year))
        top_n = int(data.get('top_n', 20))
        # 最小涨跌次数，0表示不限制
        min_count = data.get('min_count')
        if min_count is not None:
            min_count = int(min_count)
        else:
            min_count = 0
        
        # 获取数据源（优先使用请求参数，否则使用配置的数据源）
        requested_data_source = data.get('data_source')
        current_data_source = requested_data_source if requested_data_source else config.get('data_source', 'akshare')
        
        results = statistics.calculate_month_filter_statistics(
            month, start_year, end_year, top_n, data_source=current_data_source, min_count=min_count
        )
        
        # 为每个结果添加数据源信息
        for result in results:
            result['data_source'] = current_data_source
        
        return {"success": True, "data": results, "data_source": current_data_source}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/industry/statistics")
async def get_industry_statistics(data: Dict = Body(...), session_id: Optional[str] = Cookie(None)):
    """行业统计"""
    auth.require_permission(session_id, 'industry_statistics')
    try:
        month = int(data.get('month', 1))
        start_year = int(data.get('start_year', 2000))
        end_year = int(data.get('end_year', datetime.now().year))
        industry_type = data.get('industry_type', 'sw')
        
        # 获取数据源（优先使用请求参数，否则使用配置的数据源）
        requested_data_source = data.get('data_source')
        current_data_source = requested_data_source if requested_data_source else config.get('data_source', 'akshare')
        
        results = statistics.calculate_industry_statistics(
            month, start_year, end_year, industry_type, data_source=current_data_source
        )
        
        # 为每个结果添加数据源信息
        for result in results:
            result['data_source'] = current_data_source
        
        return {"success": True, "data": results, "data_source": current_data_source}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/industry/top-stocks")
async def get_industry_top_stocks(data: Dict = Body(...), session_id: Optional[str] = Cookie(None)):
    """行业中上涨概率最高的前20支股票"""
    auth.require_permission(session_id, 'industry_top_stocks')
    try:
        industry_name = data.get('industry_name')
        month = int(data.get('month', 1))
        start_year = int(data.get('start_year', 2000))
        end_year = int(data.get('end_year', datetime.now().year))
        industry_type = data.get('industry_type', 'sw')
        top_n = int(data.get('top_n', 20))
        
        if not industry_name:
            raise HTTPException(status_code=400, detail="行业名称不能为空")
        
        # 获取数据源（优先使用请求参数，否则使用配置的数据源）
        requested_data_source = data.get('data_source')
        current_data_source = requested_data_source if requested_data_source else config.get('data_source', 'akshare')
        
        results = statistics.calculate_industry_top_stocks(
            industry_name, month, start_year, end_year, industry_type, top_n, data_source=current_data_source
        )
        
        # 为每个结果添加数据源信息
        for result in results:
            result['data_source'] = current_data_source
        
        return {"success": True, "data": results, "data_source": current_data_source}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/industries")
async def get_industries(industry_type: str = 'sw'):
    """获取行业列表"""
    try:
        industries = db.get_all_industries(industry_type)
        return {"success": True, "data": industries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/data/update")
async def update_data(background_tasks: BackgroundTasks, data: Dict = Body(default={}), 
                     session_id: Optional[str] = Cookie(None)):
    """更新数据（需要数据管理权限）"""
    auth.require_permission(session_id, 'data_management')
    try:
        update_type = data.get('update_type', 'incremental')
        
        if update_progress['is_running']:
            # 如果更新正在进行，返回特殊状态，让前端显示进度
            return {
                "success": True, 
                "message": "数据更新正在进行中，请查看进度",
                "already_running": True
            }
        
        update_progress['is_running'] = True
        update_progress['current'] = 0
        update_progress['total'] = 100
        update_progress['message'] = '准备更新...'
        
        def update_task():
            try:
                # 每次更新时重新创建DataUpdater，确保使用最新配置
                current_updater = DataUpdater(db, config)
                current_updater.set_progress_callback(progress_callback)
                
                if update_type == "full":
                    # 获取更新模式：overwrite（覆盖模式）或 supplement（补充模式，默认）
                    overwrite_mode = data.get('overwrite_mode', False)
                    current_updater.update_all_data(overwrite_mode=overwrite_mode)
                else:
                    current_updater.update_incremental()
            finally:
                update_progress['is_running'] = False
        
        background_tasks.add_task(update_task)
        
        return {"success": True, "message": "数据更新已开始"}
    except Exception as e:
        update_progress['is_running'] = False
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/data/progress")
async def get_update_progress(session_id: Optional[str] = Cookie(None)):
    """获取更新进度（需要数据管理权限）"""
    auth.require_permission(session_id, 'data_management')
    return {
        "success": True,
        "data": {
            "current": update_progress['current'],
            "total": update_progress['total'],
            "message": update_progress['message'],
            "is_running": update_progress['is_running']
        }
    }


@app.get("/api/config")
async def get_config(session_id: Optional[str] = Cookie(None)):
    """获取配置（仅管理员）"""
    auth.require_admin(session_id)
    try:
        return {"success": True, "data": config.config}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/config")
async def update_config(data: Dict = Body(...), session_id: Optional[str] = Cookie(None)):
    """更新配置（仅管理员）"""
    auth.require_admin(session_id)
    try:
        for key, value in data.items():
            config.set(key, value)
        
        # 重新初始化数据源（同时更新fetcher和data_source）
        updater.fetcher = DataFetcher(config)
        updater.data_source = config.get('data_source', 'akshare')
        
        return {"success": True, "message": "配置已更新"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/data/sources")
async def get_available_data_sources(ts_code: Optional[str] = None):
    """获取可用的数据源列表"""
    try:
        sources = db.get_available_data_sources(ts_code=ts_code)
        return {"success": True, "data": sources}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/data/compare-sources")
async def compare_data_sources(data: Dict = Body(...), session_id: Optional[str] = Cookie(None)):
    """对比不同数据源的数据"""
    auth.require_permission(session_id, 'source_compare')
    try:
        ts_code = data.get('ts_code')
        trade_date = data.get('trade_date')
        month = data.get('month')
        year = data.get('year')
        
        if not ts_code:
            return {"success": False, "message": "股票代码不能为空"}
        
        compare_df = db.compare_data_sources(
            ts_code=ts_code,
            trade_date=trade_date,
            month=month,
            year=year
        )
        
        if compare_df.empty:
            return {"success": True, "data": [], "message": "没有找到对比数据，请先使用不同数据源更新数据"}
        
        # 转换为字典列表
        result = compare_df.to_dict('records')
        
        return {"success": True, "data": result}
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Error in compare_data_sources: {error_detail}")
        return {"success": False, "message": f"对比失败: {str(e)}"}


@app.get("/api/data/status")
async def get_data_status(session_id: Optional[str] = Cookie(None)):
    """获取数据状态（需要数据管理权限）"""
    auth.require_permission(session_id, 'data_management')
    try:
        stocks_df = db.get_stocks(exclude_delisted=True)
        total_stocks = len(stocks_df)
        
        # 获取所有数据源的统计信息
        data_source_stats = db.get_data_source_statistics()
        
        # 获取总体最新日期（所有数据源中的最新日期）
        latest_date = db.get_latest_trade_date()
        
        return {
            "success": True,
            "data": {
                "total_stocks": total_stocks,
                "latest_date": latest_date,
                "data_sources": data_source_stats
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Excel导出工具函数
def export_to_excel(data: List[Dict], filename: str, sheet_name: str = "Sheet1") -> StreamingResponse:
    """将数据导出为Excel文件"""
    try:
        # 创建DataFrame
        df = pd.DataFrame(data)
        
        # 创建Excel文件在内存中
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        output.seek(0)
        
        # 返回文件流
        # 处理中文文件名编码
        from urllib.parse import quote
        encoded_filename = quote(filename.encode('utf-8'))
        
        return StreamingResponse(
            io.BytesIO(output.read()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出Excel失败: {str(e)}")


@app.post("/api/export/stock-statistics")
async def export_stock_statistics(data: Dict = Body(...), session_id: Optional[str] = Cookie(None)):
    """导出单只股票统计为Excel"""
    auth.require_permission(session_id, 'export_excel')
    try:
        code = data.get('code', '').strip()
        month = int(data.get('month', 1))
        start_year = data.get('start_year')
        end_year = data.get('end_year')
        requested_data_source = data.get('data_source')
        
        if not code:
            raise HTTPException(status_code=400, detail="股票代码不能为空")
        
        # 转换年份为整数
        if start_year:
            try:
                start_year = int(start_year)
            except (ValueError, TypeError):
                start_year = None
        if end_year:
            try:
                end_year = int(end_year)
            except (ValueError, TypeError):
                end_year = None
        
        stock = db.get_stock_by_code(code)
        if not stock:
            raise HTTPException(status_code=404, detail=f"股票代码 {code} 不存在")
        
        current_data_source = requested_data_source if requested_data_source else config.get('data_source', 'akshare')
        result = statistics.calculate_stock_month_statistics(
            stock['ts_code'], month, start_year, end_year, data_source=current_data_source
        )
        
        # 准备导出数据
        export_data = [{
            '股票代码': stock.get('symbol', code),
            '股票名称': stock.get('name', ''),
            '月份': f"{month}月",
            '起始年份': start_year or '全部',
            '结束年份': end_year or '全部',
            '总次数': result.get('total_count', 0),
            '上涨次数': result.get('up_count', 0),
            '下跌次数': result.get('down_count', 0),
            '上涨概率(%)': result.get('up_probability', 0),
            '下跌概率(%)': result.get('down_probability', 0),
            '平均涨幅(%)': result.get('avg_up_pct', 0),
            '平均跌幅(%)': result.get('avg_down_pct', 0),
            '数据源': current_data_source
        }]
        
        filename = f"{stock.get('symbol', code)}_{stock.get('name', '')}_{month}月统计.xlsx"
        return export_to_excel(export_data, filename, f"{month}月统计")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@app.post("/api/export/multi-month-statistics")
async def export_multi_month_statistics(data: Dict = Body(...), session_id: Optional[str] = Cookie(None)):
    """导出单只股票多月份统计为Excel"""
    auth.require_permission(session_id, 'export_excel')
    try:
        code = data.get('code', '').strip()
        months = data.get('months', [])
        start_year = data.get('start_year')
        end_year = data.get('end_year')
        requested_data_source = data.get('data_source')
        
        if not code:
            raise HTTPException(status_code=400, detail="股票代码不能为空")
        
        if months is None or (isinstance(months, list) and len(months) == 0):
            months = list(range(1, 13))
        
        # 转换年份为整数
        if start_year:
            try:
                start_year = int(start_year)
            except (ValueError, TypeError):
                start_year = None
        if end_year:
            try:
                end_year = int(end_year)
            except (ValueError, TypeError):
                end_year = None
        
        stock = db.get_stock_by_code(code)
        if not stock:
            raise HTTPException(status_code=404, detail=f"股票代码 {code} 不存在")
        
        current_data_source = requested_data_source if requested_data_source else config.get('data_source', 'akshare')
        
        # 计算每个月份的统计
        export_data = []
        for month in months:
            stat = statistics.calculate_stock_month_statistics(
                stock['ts_code'], month, start_year, end_year, data_source=current_data_source
            )
            if stat['total_count'] > 0:
                export_data.append({
                    '月份': f"{month}月",
                    '总次数': stat.get('total_count', 0),
                    '上涨次数': stat.get('up_count', 0),
                    '下跌次数': stat.get('down_count', 0),
                    '上涨概率(%)': stat.get('up_probability', 0),
                    '下跌概率(%)': stat.get('down_probability', 0),
                    '平均涨幅(%)': stat.get('avg_up_pct', 0),
                    '平均跌幅(%)': stat.get('avg_down_pct', 0),
                    '数据源': current_data_source
                })
        
        filename = f"{stock.get('symbol', code)}_{stock.get('name', '')}_按月统计.xlsx"
        return export_to_excel(export_data, filename, "按月统计")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@app.post("/api/export/month-filter")
async def export_month_filter(data: Dict = Body(...), session_id: Optional[str] = Cookie(None)):
    """导出月份筛选统计为Excel"""
    auth.require_permission(session_id, 'export_excel')
    try:
        month = int(data.get('month', 1))
        start_year = int(data.get('start_year', 2000))
        end_year = int(data.get('end_year', datetime.now().year))
        top_n = int(data.get('top_n', 20))
        min_count = data.get('min_count')
        if min_count is not None:
            min_count = int(min_count)
        else:
            min_count = 0
        requested_data_source = data.get('data_source')
        
        current_data_source = requested_data_source if requested_data_source else config.get('data_source', 'akshare')
        results = statistics.calculate_month_filter_statistics(
            month, start_year, end_year, top_n, data_source=current_data_source, min_count=min_count
        )
        
        # 准备导出数据
        export_data = []
        for idx, item in enumerate(results, 1):
            export_data.append({
                '排名': idx,
                '股票代码': item.get('symbol', ''),
                '股票名称': item.get('name', ''),
                '上涨概率(%)': item.get('up_probability', 0),
                '上涨次数': item.get('up_count', 0),
                '下跌次数': item.get('down_count', 0),
                '平均涨幅(%)': item.get('avg_up_pct', 0),
                '平均跌幅(%)': item.get('avg_down_pct', 0),
                '总次数': item.get('total_count', 0),
                '数据源': current_data_source
            })
        
        min_count_text = f"_最小涨跌次数{min_count}" if min_count > 0 else ""
        filename = f"{month}月上涨概率前{top_n}支股票{min_count_text}.xlsx"
        return export_to_excel(export_data, filename, f"{month}月统计")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@app.post("/api/export/industry-statistics")
async def export_industry_statistics(data: Dict = Body(...), session_id: Optional[str] = Cookie(None)):
    """导出行业统计为Excel"""
    auth.require_permission(session_id, 'export_excel')
    try:
        month = int(data.get('month', 1))
        start_year = int(data.get('start_year', 2000))
        end_year = int(data.get('end_year', datetime.now().year))
        industry_type = data.get('industry_type', 'sw')
        requested_data_source = data.get('data_source')
        
        current_data_source = requested_data_source if requested_data_source else config.get('data_source', 'akshare')
        results = statistics.calculate_industry_statistics(
            month, start_year, end_year, industry_type, data_source=current_data_source
        )
        
        # 准备导出数据
        export_data = []
        for idx, item in enumerate(results, 1):
            export_data.append({
                '排名': idx,
                '行业名称': item.get('industry_name', ''),
                '股票数量': item.get('stock_count', 0),
                '上涨概率(%)': item.get('up_probability', 0),
                '上涨次数': item.get('up_count', 0),
                '下跌次数': item.get('down_count', 0),
                '平均涨幅(%)': item.get('avg_up_pct', 0),
                '平均跌幅(%)': item.get('avg_down_pct', 0),
                '总次数': item.get('total_count', 0),
                '数据源': current_data_source
            })
        
        industry_type_name = '申万' if industry_type == 'sw' else '中信'
        filename = f"{industry_type_name}行业_{month}月统计.xlsx"
        return export_to_excel(export_data, filename, f"{industry_type_name}行业统计")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@app.post("/api/export/industry-top-stocks")
async def export_industry_top_stocks(data: Dict = Body(...), session_id: Optional[str] = Cookie(None)):
    """导出行业前20支股票为Excel"""
    auth.require_permission(session_id, 'export_excel')
    try:
        industry_name = data.get('industry_name')
        month = int(data.get('month', 1))
        start_year = int(data.get('start_year', 2000))
        end_year = int(data.get('end_year', datetime.now().year))
        industry_type = data.get('industry_type', 'sw')
        top_n = int(data.get('top_n', 20))
        requested_data_source = data.get('data_source')
        
        if not industry_name:
            raise HTTPException(status_code=400, detail="行业名称不能为空")
        
        current_data_source = requested_data_source if requested_data_source else config.get('data_source', 'akshare')
        results = statistics.calculate_industry_top_stocks(
            industry_name, month, start_year, end_year, industry_type, top_n, data_source=current_data_source
        )
        
        # 准备导出数据
        export_data = []
        for idx, item in enumerate(results, 1):
            export_data.append({
                '排名': idx,
                '股票代码': item.get('symbol', ''),
                '股票名称': item.get('name', ''),
                '上涨概率(%)': item.get('up_probability', 0),
                '上涨次数': item.get('up_count', 0),
                '下跌次数': item.get('down_count', 0),
                '平均涨幅(%)': item.get('avg_up_pct', 0),
                '平均跌幅(%)': item.get('avg_down_pct', 0),
                '总次数': item.get('total_count', 0),
                '数据源': current_data_source
            })
        
        filename = f"{industry_name}_{month}月前{top_n}支股票.xlsx"
        return export_to_excel(export_data, filename, f"{industry_name}前{top_n}支")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@app.post("/api/export/compare-sources")
async def export_compare_sources(data: Dict = Body(...), session_id: Optional[str] = Cookie(None)):
    """导出数据源对比为Excel"""
    auth.require_permission(session_id, 'export_excel')
    try:
        ts_code = data.get('ts_code')
        trade_date = data.get('trade_date')
        month = data.get('month')
        year = data.get('year')
        
        if not ts_code:
            raise HTTPException(status_code=400, detail="股票代码不能为空")
        
        compare_df = db.compare_data_sources(
            ts_code=ts_code,
            trade_date=trade_date,
            month=month,
            year=year
        )
        
        if compare_df.empty:
            raise HTTPException(status_code=404, detail="未找到可对比的数据")
        
        # 转换为字典列表
        export_data = compare_df.to_dict('records')
        
        # 重命名列名为中文
        column_mapping = {
            'ts_code': '股票代码',
            'trade_date': '交易日期',
            'year': '年份',
            'month': '月份',
            'open': '开盘价',
            'close': '收盘价',
            'high': '最高价',
            'low': '最低价',
            'vol': '成交量',
            'amount': '成交额',
            'pct_chg': '涨跌幅(%)',
            'data_source': '数据源'
        }
        
        export_df = pd.DataFrame(export_data)
        export_df = export_df.rename(columns=column_mapping)
        export_data = export_df.to_dict('records')
        
        filename = f"{ts_code}_数据源对比.xlsx"
        return export_to_excel(export_data, filename, "数据源对比")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")

