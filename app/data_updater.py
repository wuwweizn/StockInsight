"""
数据更新服务
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import Callable, Optional
import time
import traceback
from app.database import Database
from app.data_fetcher import DataFetcher
from app.config import Config


class DataUpdater:
    def __init__(self, db: Database, config: Config):
        self.db = db
        self.config = config
        self.fetcher = DataFetcher(config)
        self.data_source = config.get('data_source', 'tushare')
        self.progress_callback: Optional[Callable] = None
    
    def set_progress_callback(self, callback: Callable):
        """设置进度回调函数"""
        self.progress_callback = callback
    
    def _update_progress(self, current: int, total: int, message: str = ""):
        """更新进度"""
        if self.progress_callback:
            self.progress_callback(current, total, message)
    
    def update_all_data(self, start_year: int = 2000, overwrite_mode: bool = False):
        """首次批量更新所有数据
        
        Args:
            start_year: 起始年份
            overwrite_mode: 是否使用覆盖模式
                - True: 覆盖模式，先删除当前数据源的所有数据，然后重新获取
                - False: 补充模式，只添加缺失的数据（默认）
        """
        try:
            # 1. 更新股票列表
            self._update_progress(0, 100, "正在获取股票列表...")
            stocks_df = self.fetcher.get_stock_list()
            if not stocks_df.empty:
                self.db.save_stocks(stocks_df)
                self._update_progress(10, 100, f"已获取 {len(stocks_df)} 只股票")
            else:
                self._update_progress(10, 100, "股票列表获取失败")
                return False
            
            # 2. 如果是覆盖模式，先删除当前数据源的所有数据
            if overwrite_mode:
                self._update_progress(10, 100, f"正在删除 {self.data_source} 数据源的旧数据...")
                deleted_count = self.db.delete_monthly_kline_by_source(self.data_source)
                self._update_progress(10, 100, f"已删除 {deleted_count} 条旧数据，开始重新获取...")
            
            # 3. 更新月K线数据
            current_year = datetime.now().year
            total_stocks = len(stocks_df)
            processed = 0
            
            for idx, row in stocks_df.iterrows():
                ts_code = row['ts_code']
                list_date = row['list_date']
                
                # 确定起始日期（上市日期或2000年）
                if list_date and len(list_date) == 8:
                    start_date = max(list_date, f"{start_year}0101")
                else:
                    start_date = f"{start_year}0101"
                
                end_date = datetime.now().strftime('%Y%m%d')
                
                try:
                    # 如果是补充模式，检查是否已有数据（按当前数据源）
                    if not overwrite_mode:
                        latest_date = self.db.get_latest_trade_date(ts_code, data_source=self.data_source)
                        if latest_date:
                            # 增量更新：从最新日期之后开始
                            start_date = (pd.to_datetime(latest_date, format='%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d')
                    
                    # 获取数据（添加超时保护）
                    try:
                        kline_df = self.fetcher.get_monthly_kline(ts_code, start_date, end_date)
                    except Exception as fetch_error:
                        error_msg = str(fetch_error)
                        print(f"Error fetching data for {ts_code}: {error_msg}")
                        # 更新进度，显示错误信息
                        processed += 1
                        progress = 10 + int((processed / total_stocks) * 80)
                        mode_text = "覆盖模式" if overwrite_mode else "补充模式"
                        self._update_progress(progress, 100, f"获取 {row['name']} ({ts_code}) 数据失败: {error_msg[:50]}... [{processed}/{total_stocks}]")
                        # 继续处理下一只股票
                        if self.data_source == 'akshare':
                            time.sleep(0.5)  # 即使失败也延迟一下
                        continue
                    
                    if not kline_df.empty:
                        # 计算涨跌幅（如果需要）
                        kline_df = self.fetcher.calculate_pct_chg(kline_df)
                        # 保存数据，记录数据源
                        self.db.save_monthly_kline(kline_df, data_source=self.data_source)
                    
                    processed += 1
                    progress = 10 + int((processed / total_stocks) * 80)
                    mode_text = "覆盖模式" if overwrite_mode else "补充模式"
                    self._update_progress(progress, 100, f"正在更新 {row['name']} ({ts_code})... [{processed}/{total_stocks}] [{mode_text}]")
                    
                    # 避免请求过快（akshare需要更长的延迟）
                    if self.data_source == 'akshare':
                        time.sleep(1.0)  # akshare建议延迟1秒
                    else:
                        time.sleep(0.2)
                except Exception as e:
                    error_msg = str(e)
                    error_trace = traceback.format_exc()
                    print(f"Error updating {ts_code}: {error_msg}")
                    print(f"Traceback: {error_trace}")
                    # 更新进度，显示错误信息
                    processed += 1
                    progress = 10 + int((processed / total_stocks) * 80)
                    self._update_progress(progress, 100, f"更新 {row['name']} ({ts_code}) 时出错: {error_msg[:50]}... [{processed}/{total_stocks}]")
                    continue
            
            # 4. 更新行业分类
            self._update_progress(90, 100, "正在更新行业分类...")
            self._update_industry_classification()
            
            mode_text = "覆盖模式" if overwrite_mode else "补充模式"
            self._update_progress(100, 100, f"数据更新完成！[{mode_text}]")
            return True
            
        except Exception as e:
            error_msg = str(e)
            error_trace = traceback.format_exc()
            print(f"Error in update_all_data: {error_msg}")
            print(f"Traceback: {error_trace}")
            self._update_progress(100, 100, f"数据更新失败: {error_msg}")
            return False
    
    def update_incremental(self):
        """增量更新（只更新最新数据）"""
        try:
            stocks_df = self.db.get_stocks(exclude_delisted=True)
            total_stocks = len(stocks_df)
            processed = 0
            
            for idx, row in stocks_df.iterrows():
                ts_code = row['ts_code']
                
                # 获取最新交易日期
                latest_date = self.db.get_latest_trade_date(ts_code, data_source=self.data_source)
                if latest_date:
                    start_date = (pd.to_datetime(latest_date, format='%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d')
                else:
                    # 如果没有数据，从上市日期开始
                    list_date = row['list_date']
                    start_date = list_date if list_date and len(list_date) == 8 else "20000101"
                
                end_date = datetime.now().strftime('%Y%m%d')
                
                if start_date >= end_date:
                    processed += 1
                    continue
                
                try:
                    try:
                        kline_df = self.fetcher.get_monthly_kline(ts_code, start_date, end_date)
                    except Exception as fetch_error:
                        error_msg = str(fetch_error)
                        print(f"Error fetching data for {ts_code}: {error_msg}")
                        processed += 1
                        progress = int((processed / total_stocks) * 100)
                        self._update_progress(progress, 100, f"获取 {row['name']} ({ts_code}) 数据失败: {error_msg[:50]}...")
                        time.sleep(0.2)
                        continue
                    
                    if not kline_df.empty:
                        kline_df = self.fetcher.calculate_pct_chg(kline_df)
                        self.db.save_monthly_kline(kline_df, data_source=self.data_source)
                    
                    processed += 1
                    progress = int((processed / total_stocks) * 100)
                    self._update_progress(progress, 100, f"正在更新 {row['name']} ({ts_code})...")
                    
                    time.sleep(0.2)
                except Exception as e:
                    error_msg = str(e)
                    error_trace = traceback.format_exc()
                    print(f"Error updating {ts_code}: {error_msg}")
                    print(f"Traceback: {error_trace}")
                    processed += 1
                    progress = int((processed / total_stocks) * 100)
                    self._update_progress(progress, 100, f"更新 {row['name']} ({ts_code}) 时出错: {error_msg[:50]}...")
                    continue
            
            self._update_progress(100, 100, "增量更新完成！")
            return True
            
        except Exception as e:
            error_msg = str(e)
            error_trace = traceback.format_exc()
            print(f"Error in update_incremental: {error_msg}")
            print(f"Traceback: {error_trace}")
            self._update_progress(100, 100, f"增量更新失败: {error_msg}")
            return False
    
    def _update_industry_classification(self):
        """更新行业分类"""
        try:
            # 从股票基本信息中获取行业分类
            stocks_df = self.db.get_stocks(exclude_delisted=True)
            
            # 更新申万行业分类（使用stock_basic中的industry字段）
            for idx, row in stocks_df.iterrows():
                if pd.notna(row.get('industry')) and row['industry']:
                    industry_name = row['industry']
                    self.db.save_industry(row['ts_code'], industry_name, 'L1', '', 'sw')
                    # 同时保存到中信（如果tushare的industry字段是通用分类）
                    self.db.save_industry(row['ts_code'], industry_name, 'L1', '', 'citics')
            
            # 如果数据源支持，尝试获取更详细的行业分类
            try:
                sw_industries = self.fetcher.get_industry_classification('sw')
                if sw_industries:
                    for industry_name, stock_codes in sw_industries.items():
                        for ts_code in stock_codes:
                            self.db.save_industry(ts_code, industry_name, 'L1', '', 'sw')
            except:
                pass
            
            try:
                citics_industries = self.fetcher.get_industry_classification('citics')
                if citics_industries:
                    for industry_name, stock_codes in citics_industries.items():
                        for ts_code in stock_codes:
                            self.db.save_industry(ts_code, industry_name, 'L1', '', 'citics')
            except:
                pass
        except Exception as e:
            print(f"Error updating industry classification: {e}")

