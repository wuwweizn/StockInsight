"""
统计计算模块
"""
import pandas as pd
from typing import Dict, List, Optional, Tuple
from app.database import Database


class Statistics:
    def __init__(self, db: Database):
        self.db = db
    
    def calculate_stock_month_statistics(self, ts_code: str, month: int, 
                                        start_year: int = None, end_year: int = None,
                                        data_source: str = None) -> Dict:
        """
        计算单只股票在指定月份的历史统计
        
        Args:
            ts_code: 股票代码
            month: 月份（1-12）
            start_year: 起始年份
            end_year: 结束年份
            data_source: 数据源（可选，如果不指定则使用配置的数据源）
        
        Returns:
            统计结果字典
        """
        # 获取数据源（优先使用参数，否则使用配置的数据源）
        if data_source is None:
            from app.config import Config
            config = Config()
            data_source = config.get('data_source', 'akshare')
        
        # 使用指定的数据源查询
        df = self.db.get_monthly_kline(ts_code=ts_code, month=month, 
                                      start_year=start_year, end_year=end_year,
                                      data_source=data_source)
        
        # 如果指定数据源没有数据，且没有指定数据源，则尝试所有数据源
        if df.empty and data_source is None:
            df = self.db.get_monthly_kline(ts_code=ts_code, month=month, 
                                          start_year=start_year, end_year=end_year)
        
        if df.empty:
            return {
                'ts_code': ts_code,
                'month': month,
                'total_count': 0,
                'up_count': 0,
                'down_count': 0,
                'avg_up_pct': 0,
                'avg_down_pct': 0,
                'up_probability': 0,
                'down_probability': 0
            }
        
        # 过滤有效数据（有涨跌幅的）
        df = df[df['pct_chg'].notna()]
        
        if df.empty:
            return {
                'ts_code': ts_code,
                'month': month,
                'total_count': 0,
                'up_count': 0,
                'down_count': 0,
                'avg_up_pct': 0,
                'avg_down_pct': 0,
                'up_probability': 0,
                'down_probability': 0
            }
        
        # 计算统计
        up_df = df[df['pct_chg'] > 0]
        down_df = df[df['pct_chg'] < 0]
        
        total_count = len(df)
        up_count = len(up_df)
        down_count = len(down_df)
        
        avg_up_pct = up_df['pct_chg'].mean() if up_count > 0 else 0
        avg_down_pct = down_df['pct_chg'].mean() if down_count > 0 else 0
        
        up_probability = (up_count / total_count * 100) if total_count > 0 else 0
        down_probability = (down_count / total_count * 100) if total_count > 0 else 0
        
        return {
            'ts_code': ts_code,
            'month': month,
            'total_count': total_count,
            'up_count': up_count,
            'down_count': down_count,
            'avg_up_pct': round(avg_up_pct, 2),
            'avg_down_pct': round(avg_down_pct, 2),
            'up_probability': round(up_probability, 2),
            'down_probability': round(down_probability, 2)
        }
    
    def calculate_month_filter_statistics(self, month: int, start_year: int, 
                                         end_year: int, top_n: int = 20,
                                         data_source: str = None, min_count: int = 0) -> List[Dict]:
        """
        计算月份筛选统计（按上涨概率排序前N支）
        
        Args:
            month: 月份（1-12）
            start_year: 起始年份
            end_year: 结束年份
            top_n: 返回前N支股票
            data_source: 数据源（可选，如果不指定则使用配置的数据源）
            min_count: 最小涨跌次数（上涨次数+下跌次数），0表示不限制
        
        Returns:
            统计结果列表（按上涨概率降序）
        """
        # 获取所有股票
        stocks_df = self.db.get_stocks(exclude_delisted=True)
        
        results = []
        for idx, row in stocks_df.iterrows():
            ts_code = row['ts_code']
            stat = self.calculate_stock_month_statistics(ts_code, month, start_year, end_year, data_source=data_source)
            
            # 添加股票信息
            stat['symbol'] = row['symbol']
            stat['name'] = row['name']
            
            # 只包含有数据的股票
            if stat['total_count'] > 0:
                # 检查最小涨跌次数筛选（上涨次数 + 下跌次数 >= min_count）
                total_count = stat['up_count'] + stat['down_count']
                if min_count == 0 or total_count >= min_count:
                    results.append(stat)
        
        # 按上涨概率排序
        results.sort(key=lambda x: x['up_probability'], reverse=True)
        
        return results[:top_n]
    
    def calculate_industry_statistics(self, month: int, start_year: int, end_year: int,
                                     industry_type: str = 'sw', data_source: str = None) -> List[Dict]:
        """
        计算行业统计（各行业在指定月份的上涨概率）
        
        Args:
            month: 月份（1-12）
            start_year: 起始年份
            end_year: 结束年份
            industry_type: 行业分类类型（sw/citics）
            data_source: 数据源（可选，如果不指定则使用配置的数据源）
        
        Returns:
            行业统计列表（按上涨概率降序）
        """
        # 获取所有行业
        industries = self.db.get_all_industries(industry_type)
        
        results = []
        for industry_name in industries:
            # 获取行业下的股票
            stock_codes = self.db.get_industry_stocks(industry_name, industry_type)
            
            if not stock_codes:
                continue
            
            # 统计行业整体表现
            total_up_count = 0
            total_down_count = 0
            total_count = 0
            total_up_pct_sum = 0
            total_down_pct_sum = 0
            
            for ts_code in stock_codes:
                stat = self.calculate_stock_month_statistics(ts_code, month, start_year, end_year, data_source=data_source)
                if stat['total_count'] > 0:
                    total_count += stat['total_count']
                    total_up_count += stat['up_count']
                    total_down_count += stat['down_count']
                    total_up_pct_sum += stat['avg_up_pct'] * stat['up_count']
                    total_down_pct_sum += stat['avg_down_pct'] * stat['down_count']
            
            if total_count > 0:
                avg_up_pct = total_up_pct_sum / total_up_count if total_up_count > 0 else 0
                avg_down_pct = total_down_pct_sum / total_down_count if total_down_count > 0 else 0
                up_probability = (total_up_count / total_count * 100)
                
                results.append({
                    'industry_name': industry_name,
                    'stock_count': len(stock_codes),
                    'total_count': total_count,
                    'up_count': total_up_count,
                    'down_count': total_down_count,
                    'avg_up_pct': round(avg_up_pct, 2),
                    'avg_down_pct': round(avg_down_pct, 2),
                    'up_probability': round(up_probability, 2),
                    'down_probability': round((total_down_count / total_count * 100), 2)
                })
        
        # 按上涨概率排序
        results.sort(key=lambda x: x['up_probability'], reverse=True)
        
        return results
    
    def calculate_industry_top_stocks(self, industry_name: str, month: int,
                                     start_year: int, end_year: int,
                                     industry_type: str = 'sw', top_n: int = 20,
                                     data_source: str = None) -> List[Dict]:
        """
        计算行业中上涨概率最高的前N支股票
        
        Args:
            industry_name: 行业名称
            month: 月份（1-12）
            start_year: 起始年份
            end_year: 结束年份
            industry_type: 行业分类类型（sw/citics）
            top_n: 返回前N支股票
            data_source: 数据源（可选，如果不指定则使用配置的数据源）
        
        Returns:
            股票统计列表（按上涨概率降序）
        """
        # 获取行业下的股票
        stock_codes = self.db.get_industry_stocks(industry_name, industry_type)
        
        if not stock_codes:
            return []
        
        # 获取股票信息
        stocks_df = self.db.get_stocks(exclude_delisted=True)
        
        results = []
        for ts_code in stock_codes:
            stat = self.calculate_stock_month_statistics(ts_code, month, start_year, end_year, data_source=data_source)
            
            if stat['total_count'] > 0:
                # 添加股票信息
                stock_info = stocks_df[stocks_df['ts_code'] == ts_code]
                if not stock_info.empty:
                    stat['symbol'] = stock_info.iloc[0]['symbol']
                    stat['name'] = stock_info.iloc[0]['name']
                    results.append(stat)
        
        # 按上涨概率排序
        results.sort(key=lambda x: x['up_probability'], reverse=True)
        
        return results[:top_n]

