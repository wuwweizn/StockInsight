"""
数据获取服务（支持tushare/BaoStock/FinnHub/akshare）
"""
import tushare as ts
import baostock as bs
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import time
import requests
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from app.config import Config

try:
    import akshare as ak
    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False


class DataFetcher:
    def __init__(self, config: Config):
        self.config = config
        self.data_source = config.get('data_source', 'tushare')
        self._init_data_source()
    
    def _init_data_source(self):
        """初始化数据源"""
        if self.data_source == 'tushare':
            token = self.config.get('tushare.token', '')
            if token:
                ts.set_token(token)
                self.pro = ts.pro_api()
        elif self.data_source == 'baostock':
            bs.login()
        elif self.data_source == 'finnhub':
            self.finnhub_key = self.config.get('finnhub.api_key', '')
        elif self.data_source == 'akshare':
            if not AKSHARE_AVAILABLE:
                raise ImportError("akshare未安装，请使用: pip install akshare")
    
    def get_stock_list(self) -> pd.DataFrame:
        """获取股票列表"""
        if self.data_source == 'tushare':
            return self._get_stock_list_tushare()
        elif self.data_source == 'baostock':
            return self._get_stock_list_baostock()
        elif self.data_source == 'finnhub':
            return self._get_stock_list_finnhub()
        elif self.data_source == 'akshare':
            return self._get_stock_list_akshare()
        else:
            raise ValueError(f"Unsupported data source: {self.data_source}")
    
    def _get_stock_list_tushare(self) -> pd.DataFrame:
        """从tushare获取股票列表"""
        df = self.pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,area,industry,list_date,delist_date,is_hs,exchange')
        return df
    
    def _get_stock_list_baostock(self) -> pd.DataFrame:
        """从BaoStock获取股票列表"""
        # BaoStock没有提供股票列表接口，需要从数据库或其他数据源获取
        # 优先从数据库获取已有的股票列表
        try:
            from app.database import Database
            db = Database()
            stocks_df = db.get_stocks(exclude_delisted=True)
            if not stocks_df.empty:
                return stocks_df
        except Exception as e:
            print(f"从数据库获取股票列表失败: {e}")
        
        # 如果数据库没有股票列表，尝试从tushare获取（如果配置了token）
        try:
            token = self.config.get('tushare.token', '')
            if token:
                ts.set_token(token)
                pro = ts.pro_api()
                df = pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,area,industry,list_date,delist_date,is_hs,exchange')
                return df
        except Exception as e:
            print(f"从tushare获取股票列表失败: {e}")
        
        # 如果都失败，返回空DataFrame
        print("警告: 无法获取股票列表，baostock数据源需要先有其他数据源的股票列表")
        return pd.DataFrame()
    
    def _get_stock_list_finnhub(self) -> pd.DataFrame:
        """从FinnHub获取股票列表（主要支持美股，A股支持有限）"""
        # FinnHub主要支持美股，A股数据有限
        return pd.DataFrame()
    
    def _get_stock_list_akshare(self) -> pd.DataFrame:
        """从akshare获取股票列表"""
        try:
            # akshare获取股票列表
            df = ak.stock_info_a_code_name()
            # 转换格式以匹配tushare格式
            df['ts_code'] = df['code'].apply(lambda x: f"{x}.SZ" if x.startswith('0') or x.startswith('3') else f"{x}.SH")
            df['symbol'] = df['code']
            df['name'] = df['name']
            df['list_date'] = ''  # akshare不提供上市日期
            df['delist_date'] = ''
            df['exchange'] = df['code'].apply(lambda x: 'SZ' if x.startswith('0') or x.startswith('3') else 'SH')
            return df[['ts_code', 'symbol', 'name', 'list_date', 'delist_date', 'exchange']]
        except Exception as e:
            print(f"Error fetching stock list from akshare: {e}")
            return pd.DataFrame()
    
    def get_monthly_kline(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取月K线数据"""
        if self.data_source == 'tushare':
            return self._get_monthly_kline_tushare(ts_code, start_date, end_date)
        elif self.data_source == 'baostock':
            return self._get_monthly_kline_baostock(ts_code, start_date, end_date)
        elif self.data_source == 'finnhub':
            return self._get_monthly_kline_finnhub(ts_code, start_date, end_date)
        elif self.data_source == 'akshare':
            return self._get_monthly_kline_akshare(ts_code, start_date, end_date)
        else:
            raise ValueError(f"Unsupported data source: {self.data_source}")
    
    def _get_monthly_kline_tushare(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """从tushare获取月K线（使用前复权数据）"""
        try:
            # 使用pro_bar获取前复权月线数据
            import tushare as ts
            df = ts.pro_bar(ts_code=ts_code, adj='qfq', start_date=start_date, end_date=end_date, freq='M')
            if df is not None and not df.empty:
                # 处理日期格式
                df['trade_date'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y%m%d')
                df['year'] = pd.to_datetime(df['trade_date'], format='%Y%m%d').dt.year
                df['month'] = pd.to_datetime(df['trade_date'], format='%Y%m%d').dt.month
                # 确保有ts_code字段
                if 'ts_code' not in df.columns:
                    df['ts_code'] = ts_code
                # 计算涨跌幅（如果需要）
                df = self.calculate_pct_chg(df)
                return df
        except Exception as e:
            print(f"Error fetching monthly adjusted data from tushare: {e}")
        
        # 如果月线数据获取失败，从日线前复权数据计算月线
        try:
            import tushare as ts
            df = ts.pro_bar(ts_code=ts_code, adj='qfq', start_date=start_date, end_date=end_date, freq='D')
            if df is not None and not df.empty:
                df['trade_date'] = pd.to_datetime(df['trade_date'])
                df['year'] = df['trade_date'].dt.year
                df['month'] = df['trade_date'].dt.month
                
                # 按月聚合
                # 开盘价：取每月第一个交易日的开盘价
                # 收盘价：取每月最后一天的收盘价
                monthly_first = df.groupby(['year', 'month']).first().reset_index()
                monthly_last = df.groupby(['year', 'month']).last().reset_index()
                
                # 合并数据
                monthly_df = monthly_last[['year', 'month', 'trade_date']].copy()
                monthly_df['trade_date'] = monthly_df['trade_date'].dt.strftime('%Y%m%d')
                monthly_df['ts_code'] = ts_code
                monthly_df['open'] = monthly_first['open'].values  # 第一个交易日的开盘价
                monthly_df['close'] = monthly_last['close'].values  # 最后一天的收盘价
                
                # 计算月K涨跌幅：需要获取上月的收盘价
                monthly_df = monthly_df.sort_values('trade_date')
                for idx, row in monthly_df.iterrows():
                    year = row['year']
                    month = row['month']
                    # 计算上月日期
                    if month == 1:
                        prev_year = year - 1
                        prev_month = 12
                    else:
                        prev_year = year
                        prev_month = month - 1
                    
                    # 获取上月最后一天的收盘价
                    try:
                        prev_start = f"{prev_year}{prev_month:02d}01"
                        prev_end = f"{prev_year}{prev_month:02d}31"
                        prev_df = ts.pro_bar(ts_code=ts_code, adj='qfq', start_date=prev_start, end_date=prev_end, freq='D')
                        if prev_df is not None and not prev_df.empty:
                            prev_df = prev_df.sort_values('trade_date')
                            prev_close = prev_df.iloc[-1]['close']
                            current_close = row['close']
                            if pd.notna(prev_close) and pd.notna(current_close) and prev_close > 0:
                                monthly_df.loc[idx, 'pct_chg'] = (current_close - prev_close) / prev_close * 100
                    except:
                        pass
                
                # 如果没有pct_chg，使用close的pct_change
                if 'pct_chg' not in monthly_df.columns or monthly_df['pct_chg'].isna().all():
                    monthly_df = self.calculate_pct_chg(monthly_df)
                
                return monthly_df
        except Exception as e:
            print(f"Error fetching daily adjusted data from tushare: {e}")
        
        return pd.DataFrame()
    
    def _get_monthly_kline_baostock(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """从BaoStock获取月K线"""
        try:
            # BaoStock代码格式转换（如000001.SZ -> sz.000001）
            if ts_code.endswith('.SZ'):
                code = f"sz.{ts_code.replace('.SZ', '')}"
            elif ts_code.endswith('.SH'):
                code = f"sh.{ts_code.replace('.SH', '')}"
            else:
                # 如果没有后缀，根据代码判断
                if ts_code.startswith('0') or ts_code.startswith('3'):
                    code = f"sz.{ts_code}"
                else:
                    code = f"sh.{ts_code}"
            
            # BaoStock日期格式需要是 YYYY-MM-DD
            start_date_formatted = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
            end_date_formatted = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"
            
            rs = bs.query_history_k_data_plus(
                code,
                "date,open,high,low,close,volume,amount",
                start_date=start_date_formatted,
                end_date=end_date_formatted,
                frequency="m",
                adjustflag="3"  # 前复权
            )
            
            # 检查返回结果
            if rs is None:
                print(f"BaoStock查询返回None: {ts_code}")
                return pd.DataFrame()
            
            if rs.error_code != '0':
                print(f"BaoStock查询错误 {ts_code}: {rs.error_msg}")
                return pd.DataFrame()
            
            df = rs.get_data()
            if df.empty:
                return pd.DataFrame()
            
            # 确保有date列
            if 'date' not in df.columns:
                print(f"BaoStock返回数据缺少date列: {ts_code}")
                return pd.DataFrame()
            
            # 转换数值列为数值类型（baostock返回的是字符串）
            numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'amount']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df['ts_code'] = ts_code
            df['trade_date'] = pd.to_datetime(df['date']).dt.strftime('%Y%m%d')
            df['year'] = pd.to_datetime(df['date']).dt.year
            df['month'] = pd.to_datetime(df['date']).dt.month
            df['pct_chg'] = df['close'].pct_change() * 100
            df = df.rename(columns={'volume': 'vol'})
            
            return df[['ts_code', 'trade_date', 'year', 'month', 'open', 'close', 'high', 'low', 'vol', 'amount', 'pct_chg']]
        except Exception as e:
            print(f"Error fetching baostock data for {ts_code}: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    def _get_monthly_kline_finnhub(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """从FinnHub获取月K线（A股支持有限）"""
        # FinnHub主要支持美股，A股数据有限，这里返回空
        return pd.DataFrame()
    
    def _get_monthly_kline_akshare(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """从akshare获取月K线（前复权）"""
        try:
            # akshare的代码格式：去掉.SZ或.SH后缀
            code = ts_code.replace('.SZ', '').replace('.SH', '')
            
            # 为了计算第一个月的涨跌幅，需要获取上个月最后一天的数据
            # 扩展起始日期到上个月
            start_dt = pd.to_datetime(start_date, format='%Y%m%d')
            prev_month_start = (start_dt - pd.DateOffset(months=1)).replace(day=1)
            extended_start = prev_month_start.strftime('%Y%m%d')
            
            # 使用超时机制获取日线数据（前复权），防止卡住
            def fetch_data():
                return ak.stock_zh_a_hist(symbol=code, period="daily", start_date=extended_start, end_date=end_date, adjust="qfq")
            
            # 设置超时时间为30秒
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(fetch_data)
                try:
                    df = future.result(timeout=30)
                except FutureTimeoutError:
                    raise TimeoutError(f"获取 {ts_code} 数据超时（超过30秒）")
                except Exception as e:
                    raise Exception(f"获取 {ts_code} 数据失败: {str(e)}")
            
            if df is None or df.empty:
                return pd.DataFrame()
            
            # 找到日期、开盘、收盘列
            date_col = None
            open_col = None
            close_col = None
            
            for col in df.columns:
                if '日期' in str(col) or 'date' in str(col).lower():
                    date_col = col
                if '开盘' in str(col) or 'open' in str(col).lower():
                    open_col = col
                if '收盘' in str(col) or 'close' in str(col).lower():
                    close_col = col
            
            if not (date_col and open_col and close_col):
                return pd.DataFrame()
            
            # 转换日期格式
            df[date_col] = pd.to_datetime(df[date_col])
            df['year'] = df[date_col].dt.year
            df['month'] = df[date_col].dt.month
            df['trade_date'] = df[date_col].dt.strftime('%Y%m%d')
            
            # 过滤掉上个月的数据（只保留请求范围内的数据）
            start_dt = pd.to_datetime(start_date, format='%Y%m%d')
            end_dt = pd.to_datetime(end_date, format='%Y%m%d')
            df = df[(df[date_col] >= start_dt) & (df[date_col] <= end_dt)]
            
            if df.empty:
                return pd.DataFrame()
            
            # 获取上个月最后一天的收盘价（用于计算第一个月的涨跌幅）
            # 使用超时机制获取上个月数据
            def fetch_prev_month():
                return ak.stock_zh_a_hist(symbol=code, period="daily", 
                                         start_date=prev_month_start.strftime('%Y%m%d'), 
                                         end_date=(start_dt - pd.Timedelta(days=1)).strftime('%Y%m%d'), 
                                         adjust="qfq")
            
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(fetch_prev_month)
                try:
                    prev_month_df = future.result(timeout=15)
                except FutureTimeoutError:
                    prev_month_df = None  # 超时则跳过
                except Exception:
                    prev_month_df = None  # 出错则跳过
            prev_close = None
            if prev_month_df is not None and not prev_month_df.empty:
                prev_date_col = None
                prev_close_col = None
                for col in prev_month_df.columns:
                    if '日期' in str(col) or 'date' in str(col).lower():
                        prev_date_col = col
                    if '收盘' in str(col) or 'close' in str(col).lower():
                        prev_close_col = col
                if prev_date_col and prev_close_col:
                    prev_month_df = prev_month_df.sort_values(prev_date_col)
                    prev_close = prev_month_df.iloc[-1][prev_close_col]
            
            # 按月聚合
            # 开盘价：取每月第一个交易日的开盘价
            # 收盘价：取每月最后一天的收盘价
            monthly_first = df.groupby(['year', 'month']).first().reset_index()
            monthly_last = df.groupby(['year', 'month']).last().reset_index()
            
            # 合并数据
            monthly_df = monthly_last[['year', 'month', 'trade_date']].copy()
            monthly_df['ts_code'] = ts_code
            monthly_df['open'] = monthly_first[open_col].values  # 第一个交易日的开盘价
            monthly_df['close'] = monthly_last[close_col].values  # 最后一天的收盘价
            
            # 获取最高、最低、成交量、成交额
            if '最高' in df.columns:
                monthly_df['high'] = df.groupby(['year', 'month'])['最高'].max().values
            else:
                monthly_df['high'] = monthly_df['close']
            
            if '最低' in df.columns:
                monthly_df['low'] = df.groupby(['year', 'month'])['最低'].min().values
            else:
                monthly_df['low'] = monthly_df['close']
            
            if '成交量' in df.columns:
                monthly_df['vol'] = df.groupby(['year', 'month'])['成交量'].sum().values
            else:
                monthly_df['vol'] = 0
            
            if '成交额' in df.columns:
                monthly_df['amount'] = df.groupby(['year', 'month'])['成交额'].sum().values
            else:
                monthly_df['amount'] = 0
            
            # 计算月K涨跌幅
            monthly_df = monthly_df.sort_values('trade_date')
            prev_month_close = prev_close
            
            for idx, row in monthly_df.iterrows():
                current_close = row['close']
                current_open = row['open']
                
                if prev_month_close is not None and pd.notna(prev_month_close) and prev_month_close > 0:
                    # 有上个月数据，使用上个月收盘价作为基准
                    if pd.notna(current_close):
                        monthly_df.loc[idx, 'pct_chg'] = (current_close - prev_month_close) / prev_month_close * 100
                elif pd.notna(current_open) and current_open > 0:
                    # 没有上个月数据（可能是新股上市首月），使用当月开盘价作为基准
                    if pd.notna(current_close):
                        monthly_df.loc[idx, 'pct_chg'] = (current_close - current_open) / current_open * 100
                
                # 更新prev_month_close为当前月的收盘价，用于下个月的计算
                prev_month_close = row['close']
            
            # 如果没有pct_chg，使用close的pct_change
            if 'pct_chg' not in monthly_df.columns or monthly_df['pct_chg'].isna().all():
                monthly_df = self.calculate_pct_chg(monthly_df)
            
            return monthly_df[['ts_code', 'trade_date', 'year', 'month', 'open', 'close', 'high', 'low', 'vol', 'amount', 'pct_chg']]
        except Exception as e:
            print(f"Error fetching monthly kline from akshare: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame()
    
    def get_industry_classification(self, industry_type: str = 'sw') -> Dict[str, List[str]]:
        """获取行业分类"""
        if self.data_source == 'tushare':
            return self._get_industry_tushare(industry_type)
        else:
            return {}
    
    def _get_industry_tushare(self, industry_type: str = 'sw') -> Dict[str, List[str]]:
        """从tushare获取行业分类"""
        try:
            # 使用stock_basic获取行业信息
            stocks_df = self.pro.stock_basic(exchange='', list_status='L', 
                                            fields='ts_code,industry')
            
            industry_dict = {}
            for idx, row in stocks_df.iterrows():
                if pd.notna(row['industry']) and row['industry']:
                    industry_name = row['industry']
                    if industry_name not in industry_dict:
                        industry_dict[industry_name] = []
                    industry_dict[industry_name].append(row['ts_code'])
            
            return industry_dict
        except Exception as e:
            print(f"Error fetching industry classification: {e}")
            # 如果失败，尝试使用index_classify
            try:
                if industry_type == 'sw':
                    df = self.pro.index_classify(level='L1', src='SW2021')
                elif industry_type == 'citics':
                    df = self.pro.index_classify(level='L1', src='CSI')
                else:
                    return {}
                
                industry_dict = {}
                for idx_code in df['index_code'].unique():
                    idx_info = df[df['index_code'] == idx_code].iloc[0]
                    industry_name = idx_info['industry_name']
                    cons_df = self.pro.index_weight(index_code=idx_code)
                    if not cons_df.empty:
                        industry_dict[industry_name] = cons_df['con_code'].tolist()
                return industry_dict
            except Exception as e2:
                print(f"Error with index_classify: {e2}")
                return {}
    
    def calculate_pct_chg(self, df: pd.DataFrame) -> pd.DataFrame:
        """计算涨跌幅（如果数据源没有提供）"""
        if 'pct_chg' in df.columns and not df['pct_chg'].isna().all():
            # 检查pct_chg的格式：如果最大值小于1，可能是小数形式，需要转换为百分比
            valid_pct = df[df['pct_chg'].notna()]['pct_chg']
            if len(valid_pct) > 0:
                max_abs = valid_pct.abs().max()
                # 如果绝对值最大值小于1，可能是小数形式（如0.058），需要乘以100
                if max_abs < 1:
                    df['pct_chg'] = df['pct_chg'] * 100
            return df
        
        df = df.sort_values('trade_date')
        df['pct_chg'] = df['close'].pct_change() * 100
        return df

