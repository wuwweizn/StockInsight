"""
权限定义和管理
"""
from typing import List, Dict

# 权限定义
PERMISSIONS = {
    'stock_analysis_single': {
        'code': 'stock_analysis_single',
        'name': '单只股票分析（单月统计）',
        'description': '可以查询单只股票的单月统计数据'
    },
    'stock_analysis_multi': {
        'code': 'stock_analysis_multi',
        'name': '单只股票分析（多月份统计）',
        'description': '可以查询单只股票的多月份统计数据'
    },
    'month_filter': {
        'code': 'month_filter',
        'name': '月份筛选统计',
        'description': '可以按月份筛选股票统计数据'
    },
    'industry_statistics': {
        'code': 'industry_statistics',
        'name': '行业分析（行业统计）',
        'description': '可以查询行业统计数据'
    },
    'industry_top_stocks': {
        'code': 'industry_top_stocks',
        'name': '行业分析（行业前N支股票）',
        'description': '可以查询行业前N支股票'
    },
    'source_compare': {
        'code': 'source_compare',
        'name': '数据源对比',
        'description': '可以对比不同数据源的数据'
    },
    'export_excel': {
        'code': 'export_excel',
        'name': 'Excel导出',
        'description': '可以导出查询结果为Excel文件'
    },
    'data_management': {
        'code': 'data_management',
        'name': '数据管理',
        'description': '可以查看数据状态、更新数据（全量/增量）'
    }
}

# 所有权限代码列表
ALL_PERMISSIONS = list(PERMISSIONS.keys())


def get_permission_name(code: str) -> str:
    """获取权限名称"""
    return PERMISSIONS.get(code, {}).get('name', code)


def get_all_permissions() -> List[Dict]:
    """获取所有权限列表"""
    return [PERMISSIONS[code] for code in ALL_PERMISSIONS]

