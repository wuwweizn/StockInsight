"""
数据库模型和操作
"""
import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pandas as pd


class Database:
    def __init__(self, db_path: str = None):
        # 支持环境变量指定数据库路径（用于Docker部署）
        if db_path is None:
            import os
            db_path = os.getenv("DB_PATH", "stock_data.db")
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """获取数据库连接"""
        return sqlite3.connect(self.db_path)
    
    def init_database(self):
        """初始化数据库表结构"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 股票基本信息表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stocks (
                ts_code TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                name TEXT NOT NULL,
                area TEXT,
                industry TEXT,
                list_date TEXT,
                delist_date TEXT,
                is_hs TEXT,
                exchange TEXT
            )
        """)
        
        # 行业分类表（申万）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS industry_sw (
                ts_code TEXT,
                industry_name TEXT,
                level TEXT,
                parent_code TEXT,
                PRIMARY KEY (ts_code, industry_name)
            )
        """)
        
        # 行业分类表（中信）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS industry_citics (
                ts_code TEXT,
                industry_name TEXT,
                level TEXT,
                parent_code TEXT,
                PRIMARY KEY (ts_code, industry_name)
            )
        """)
        
        # 用户表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                is_active INTEGER NOT NULL DEFAULT 1,
                valid_until TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT
            )
        """)
        
        # 会话表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # 系统配置表（用于存储会话时长等系统配置）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT
            )
        """)
        
        # 用户权限表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                permission_code TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, permission_code)
            )
        """)
        
        # 初始化默认管理员账号（如果不存在）
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
        if cursor.fetchone()[0] == 0:
            import bcrypt
            password_hash = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, is_active, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, ('admin', password_hash, 'admin', 1, datetime.now().strftime('%Y%m%d%H%M%S')))
        
        # 初始化系统配置（会话时长，默认24小时）
        cursor.execute("SELECT COUNT(*) FROM system_config WHERE key = 'session_duration_hours'")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO system_config (key, value, updated_at)
                VALUES (?, ?, ?)
            """, ('session_duration_hours', '24', datetime.now().strftime('%Y%m%d%H%M%S')))
        
        # 提交所有更改
        conn.commit()
        
        # 月K线数据表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS monthly_kline (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_code TEXT NOT NULL,
                trade_date TEXT NOT NULL,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                open REAL,
                close REAL,
                high REAL,
                low REAL,
                vol REAL,
                amount REAL,
                pct_chg REAL,
                data_source TEXT DEFAULT 'akshare',
                UNIQUE(ts_code, trade_date, data_source)
            )
        """)
        
        # 检查表结构和约束
        cursor.execute("PRAGMA table_info(monthly_kline)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # 检查表定义中的UNIQUE约束
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='monthly_kline'")
        table_sql = cursor.fetchone()
        has_old_constraint = False
        if table_sql and 'UNIQUE(ts_code, trade_date)' in table_sql[0] and 'UNIQUE(ts_code, trade_date, data_source)' not in table_sql[0]:
            has_old_constraint = True
        
        if 'data_source' not in columns or has_old_constraint:
            # 需要重建表
            print("检测到旧的表结构，正在重建表以支持多数据源...")
            
            # 备份数据
            cursor.execute("SELECT * FROM monthly_kline")
            old_data = cursor.fetchall()
            old_columns = [desc[0] for desc in cursor.description]
            
            # 删除旧表
            cursor.execute("DROP TABLE IF EXISTS monthly_kline")
            
            # 创建新表
            cursor.execute("""
                CREATE TABLE monthly_kline (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_code TEXT NOT NULL,
                    trade_date TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    month INTEGER NOT NULL,
                    open REAL,
                    close REAL,
                    high REAL,
                    low REAL,
                    vol REAL,
                    amount REAL,
                    pct_chg REAL,
                    data_source TEXT DEFAULT 'akshare',
                    UNIQUE(ts_code, trade_date, data_source)
                )
            """)
            
            # 恢复数据（如果有data_source字段则使用，否则默认为akshare）
            if old_data:
                data_source_col_idx = old_columns.index('data_source') if 'data_source' in old_columns else None
                for row in old_data:
                    data_source = row[data_source_col_idx] if data_source_col_idx is not None and row[data_source_col_idx] else 'akshare'
                    cursor.execute("""
                        INSERT INTO monthly_kline 
                        (ts_code, trade_date, year, month, open, close, high, low, vol, amount, pct_chg, data_source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row[old_columns.index('ts_code')],
                        row[old_columns.index('trade_date')],
                        row[old_columns.index('year')],
                        row[old_columns.index('month')],
                        row[old_columns.index('open')],
                        row[old_columns.index('close')],
                        row[old_columns.index('high')],
                        row[old_columns.index('low')],
                        row[old_columns.index('vol')],
                        row[old_columns.index('amount')],
                        row[old_columns.index('pct_chg')],
                        data_source
                    ))
            
            print("✓ 表重建完成")
        else:
            # 如果字段已存在，确保有唯一索引
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_monthly_kline_unique ON monthly_kline(ts_code, trade_date, data_source)")
        
        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_monthly_kline_code ON monthly_kline(ts_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_monthly_kline_date ON monthly_kline(trade_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_monthly_kline_year_month ON monthly_kline(year, month)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stocks_delist ON stocks(delist_date)")
        
        conn.commit()
        conn.close()
    
    def save_stocks(self, stocks_df: pd.DataFrame):
        """保存股票基本信息"""
        conn = self.get_connection()
        stocks_df.to_sql('stocks', conn, if_exists='replace', index=False)
        conn.commit()
        conn.close()
    
    def save_monthly_kline(self, kline_df: pd.DataFrame, data_source: str = 'akshare'):
        """保存月K线数据（使用INSERT OR REPLACE避免重复，支持多数据源）"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        for idx, row in kline_df.iterrows():
            cursor.execute("""
                INSERT OR REPLACE INTO monthly_kline 
                (ts_code, trade_date, year, month, open, close, high, low, vol, amount, pct_chg, data_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row.get('ts_code'),
                row.get('trade_date'),
                row.get('year'),
                row.get('month'),
                row.get('open'),
                row.get('close'),
                row.get('high'),
                row.get('low'),
                row.get('vol'),
                row.get('amount'),
                row.get('pct_chg'),
                data_source
            ))
        
        conn.commit()
        conn.close()
    
    def delete_monthly_kline_by_source(self, data_source: str):
        """删除指定数据源的所有月K线数据"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM monthly_kline WHERE data_source = ?", (data_source,))
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted_count
    
    # ========== 用户和权限管理方法 ==========
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """根据用户名获取用户信息"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, password_hash, role, is_active, valid_until, created_at
            FROM users
            WHERE username = ?
        """, (username,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'username': row[1],
                'password_hash': row[2],
                'role': row[3],
                'is_active': bool(row[4]),
                'valid_until': row[5],
                'created_at': row[6]
            }
        return None
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """根据ID获取用户信息"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, password_hash, role, is_active, valid_until, created_at
            FROM users
            WHERE id = ?
        """, (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'username': row[1],
                'password_hash': row[2],
                'role': row[3],
                'is_active': bool(row[4]),
                'valid_until': row[5],
                'created_at': row[6]
            }
        return None
    
    def create_user(self, username: str, password: str, role: str = 'user', valid_until: str = None) -> int:
        """创建用户"""
        import bcrypt
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, is_active, valid_until, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (username, password_hash, role, 1, valid_until, datetime.now().strftime('%Y%m%d%H%M%S')))
            user_id = cursor.lastrowid
            conn.commit()
            return user_id
        except sqlite3.IntegrityError:
            raise ValueError(f"用户名 {username} 已存在")
        finally:
            conn.close()
    
    def update_user(self, user_id: int, username: str = None, password: str = None, 
                   role: str = None, is_active: bool = None, valid_until: str = None):
        """更新用户信息"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if username is not None:
            updates.append("username = ?")
            params.append(username)
        if password is not None:
            import bcrypt
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            updates.append("password_hash = ?")
            params.append(password_hash)
        if role is not None:
            updates.append("role = ?")
            params.append(role)
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)
        if valid_until is not None:
            updates.append("valid_until = ?")
            params.append(valid_until)
        
        if updates:
            updates.append("updated_at = ?")
            params.append(datetime.now().strftime('%Y%m%d%H%M%S'))
            params.append(user_id)
            
            cursor.execute(f"""
                UPDATE users
                SET {', '.join(updates)}
                WHERE id = ?
            """, params)
            conn.commit()
        
        conn.close()
    
    def delete_user(self, user_id: int):
        """删除用户"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    
    def get_all_users(self) -> List[Dict]:
        """获取所有用户列表"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, role, is_active, valid_until, created_at
            FROM users
            ORDER BY created_at DESC
        """)
        users = []
        for row in cursor.fetchall():
            users.append({
                'id': row[0],
                'username': row[1],
                'role': row[2],
                'is_active': bool(row[3]),
                'valid_until': row[4],
                'created_at': row[5]
            })
        conn.close()
        return users
    
    def create_session(self, user_id: int, session_id: str, expires_at: str) -> bool:
        """创建会话"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO sessions (session_id, user_id, expires_at, created_at)
                VALUES (?, ?, ?, ?)
            """, (session_id, user_id, expires_at, datetime.now().strftime('%Y%m%d%H%M%S')))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # 如果session_id已存在，更新它
            cursor.execute("""
                UPDATE sessions
                SET user_id = ?, expires_at = ?, created_at = ?
                WHERE session_id = ?
            """, (user_id, expires_at, datetime.now().strftime('%Y%m%d%H%M%S'), session_id))
            conn.commit()
            return True
        finally:
            conn.close()
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """获取会话信息"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.session_id, s.user_id, s.expires_at, u.username, u.role, u.is_active
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.session_id = ?
        """, (session_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            expires_at = datetime.strptime(row[2], '%Y%m%d%H%M%S')
            if expires_at < datetime.now():
                # 会话已过期，删除它
                self.delete_session(session_id)
                return None
            
            return {
                'session_id': row[0],
                'user_id': row[1],
                'expires_at': row[2],
                'username': row[3],
                'role': row[4],
                'is_active': bool(row[5])
            }
        return None
    
    def delete_session(self, session_id: str):
        """删除会话"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()
    
    def cleanup_expired_sessions(self):
        """清理过期会话"""
        conn = self.get_connection()
        cursor = conn.cursor()
        current_time = datetime.now().strftime('%Y%m%d%H%M%S')
        cursor.execute("DELETE FROM sessions WHERE expires_at < ?", (current_time,))
        conn.commit()
        conn.close()
    
    def get_system_config(self, key: str, default: str = None) -> Optional[str]:
        """获取系统配置"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_config WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else default
    
    def set_system_config(self, key: str, value: str):
        """设置系统配置"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO system_config (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (key, value, datetime.now().strftime('%Y%m%d%H%M%S')))
        conn.commit()
        conn.close()
    
    # ========== 权限管理方法 ==========
    
    def get_user_permissions(self, user_id: int) -> List[str]:
        """获取用户权限列表"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT permission_code
            FROM user_permissions
            WHERE user_id = ?
        """, (user_id,))
        permissions = [row[0] for row in cursor.fetchall()]
        conn.close()
        return permissions
    
    def set_user_permissions(self, user_id: int, permission_codes: List[str]):
        """设置用户权限（覆盖原有权限）"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 先删除所有现有权限
        cursor.execute("DELETE FROM user_permissions WHERE user_id = ?", (user_id,))
        
        # 添加新权限
        current_time = datetime.now().strftime('%Y%m%d%H%M%S')
        for code in permission_codes:
            cursor.execute("""
                INSERT INTO user_permissions (user_id, permission_code, created_at)
                VALUES (?, ?, ?)
            """, (user_id, code, current_time))
        
        conn.commit()
        conn.close()
    
    def add_user_permission(self, user_id: int, permission_code: str):
        """添加单个权限"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO user_permissions (user_id, permission_code, created_at)
                VALUES (?, ?, ?)
            """, (user_id, permission_code, datetime.now().strftime('%Y%m%d%H%M%S')))
            conn.commit()
        except sqlite3.IntegrityError:
            # 权限已存在，忽略
            pass
        finally:
            conn.close()
    
    def remove_user_permission(self, user_id: int, permission_code: str):
        """移除单个权限"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM user_permissions
            WHERE user_id = ? AND permission_code = ?
        """, (user_id, permission_code))
        conn.commit()
        conn.close()
    
    def has_permission(self, user_id: int, permission_code: str) -> bool:
        """检查用户是否有指定权限"""
        # 管理员始终拥有所有权限
        user = self.get_user_by_id(user_id)
        if user and user['role'] == 'admin':
            return True
        
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*)
            FROM user_permissions
            WHERE user_id = ? AND permission_code = ?
        """, (user_id, permission_code))
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    
    def get_stocks(self, exclude_delisted: bool = True) -> pd.DataFrame:
        """获取股票列表"""
        conn = self.get_connection()
        query = "SELECT * FROM stocks"
        if exclude_delisted:
            query += " WHERE delist_date IS NULL OR delist_date = ''"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    
    def get_stock_by_code(self, code: str) -> Optional[Dict]:
        """根据代码获取股票信息"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 先获取表结构，确定有哪些列
        cursor.execute("PRAGMA table_info(stocks)")
        columns_info = cursor.fetchall()
        column_names = [col[1] for col in columns_info]
        
        # 构建查询语句
        if column_names:
            select_cols = ', '.join(column_names)
            cursor.execute(f"""
                SELECT {select_cols}
                FROM stocks 
                WHERE symbol = ? OR ts_code = ?
            """, (code, code))
        else:
            # 如果表不存在或为空，使用默认列
            cursor.execute("""
                SELECT ts_code, symbol, name, list_date, delist_date, exchange 
                FROM stocks 
                WHERE symbol = ? OR ts_code = ?
            """, (code, code))
            column_names = ['ts_code', 'symbol', 'name', 'list_date', 'delist_date', 'exchange']
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            result = {}
            for i, col_name in enumerate(column_names):
                if i < len(row):
                    result[col_name] = row[i]
                else:
                    result[col_name] = None
            return result
        return None
    
    def search_stocks(self, keyword: str, limit: int = 20) -> List[Dict]:
        """根据关键词搜索股票（支持代码和名称）"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 模糊搜索：匹配代码或名称
        keyword_pattern = f"%{keyword}%"
        cursor.execute("""
            SELECT ts_code, symbol, name, exchange
            FROM stocks 
            WHERE (symbol LIKE ? OR ts_code LIKE ? OR name LIKE ?)
            AND (delist_date IS NULL OR delist_date = '')
            ORDER BY 
                CASE 
                    WHEN symbol = ? THEN 1
                    WHEN ts_code = ? THEN 2
                    WHEN symbol LIKE ? THEN 3
                    WHEN ts_code LIKE ? THEN 4
                    WHEN name LIKE ? THEN 5
                    ELSE 6
                END,
                symbol
            LIMIT ?
        """, (keyword_pattern, keyword_pattern, keyword_pattern, 
              keyword, keyword, f"{keyword}%", f"{keyword}%", f"{keyword}%", limit))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'ts_code': row[0],
                'symbol': row[1],
                'name': row[2],
                'exchange': row[3]
            })
        
        conn.close()
        return results
    
    def get_monthly_kline(self, ts_code: str = None, year: int = None, 
                          month: int = None, start_year: int = None, 
                          end_year: int = None, data_source: str = None) -> pd.DataFrame:
        """获取月K线数据（支持按数据源过滤）"""
        conn = self.get_connection()
        query = "SELECT * FROM monthly_kline WHERE 1=1"
        params = []
        
        if ts_code:
            query += " AND ts_code = ?"
            params.append(ts_code)
        if year:
            query += " AND year = ?"
            params.append(year)
        if month:
            query += " AND month = ?"
            params.append(month)
        if start_year:
            query += " AND year >= ?"
            params.append(start_year)
        if end_year:
            query += " AND year <= ?"
            params.append(end_year)
        if data_source:
            query += " AND data_source = ?"
            params.append(data_source)
        
        query += " ORDER BY trade_date"
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    
    def get_available_data_sources(self, ts_code: str = None) -> List[str]:
        """获取可用的数据源列表"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if ts_code:
            cursor.execute("SELECT DISTINCT data_source FROM monthly_kline WHERE ts_code = ?", (ts_code,))
        else:
            cursor.execute("SELECT DISTINCT data_source FROM monthly_kline")
        
        sources = [row[0] for row in cursor.fetchall() if row[0]]
        conn.close()
        return sources
    
    def get_data_source_statistics(self) -> List[Dict]:
        """获取每个数据源的统计信息（数据量和最新日期）"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 查询每个数据源的统计信息
        cursor.execute("""
            SELECT 
                data_source,
                COUNT(*) as data_count,
                MAX(trade_date) as latest_date,
                COUNT(DISTINCT ts_code) as stock_count
            FROM monthly_kline
            GROUP BY data_source
            ORDER BY data_source
        """)
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'data_source': row[0],
                'data_count': row[1],
                'latest_date': row[2],
                'stock_count': row[3]
            })
        
        conn.close()
        return results
    
    def compare_data_sources(self, ts_code: str, trade_date: str = None, 
                            month: int = None, year: int = None) -> pd.DataFrame:
        """对比不同数据源的数据"""
        conn = self.get_connection()
        query = """
            SELECT ts_code, trade_date, year, month, open, close, pct_chg, data_source
            FROM monthly_kline 
            WHERE ts_code = ?
        """
        params = [ts_code]
        
        if trade_date:
            query += " AND trade_date = ?"
            params.append(trade_date)
        if month:
            query += " AND month = ?"
            params.append(month)
        if year:
            query += " AND year = ?"
            params.append(year)
        
        query += " ORDER BY trade_date, data_source"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    
    def get_latest_trade_date(self, ts_code: str = None, data_source: str = None) -> Optional[str]:
        """获取最新的交易日期（支持按数据源过滤）"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = "SELECT MAX(trade_date) FROM monthly_kline WHERE 1=1"
        params = []
        
        if ts_code:
            query += " AND ts_code = ?"
            params.append(ts_code)
        
        if data_source:
            query += " AND data_source = ?"
            params.append(data_source)
        
        cursor.execute(query, params)
        result = cursor.fetchone()
        conn.close()
        return result[0] if result and result[0] else None
    
    def save_industry(self, ts_code: str, industry_name: str, level: str, 
                     parent_code: str, industry_type: str = 'sw'):
        """保存行业分类"""
        conn = self.get_connection()
        cursor = conn.cursor()
        table = 'industry_sw' if industry_type == 'sw' else 'industry_citics'
        cursor.execute(f"""
            INSERT OR REPLACE INTO {table} (ts_code, industry_name, level, parent_code)
            VALUES (?, ?, ?, ?)
        """, (ts_code, industry_name, level, parent_code))
        conn.commit()
        conn.close()
    
    def get_industry_stocks(self, industry_name: str, industry_type: str = 'sw') -> List[str]:
        """获取行业下的股票代码列表"""
        conn = self.get_connection()
        table = 'industry_sw' if industry_type == 'sw' else 'industry_citics'
        cursor = conn.cursor()
        cursor.execute(f"SELECT DISTINCT ts_code FROM {table} WHERE industry_name = ?", (industry_name,))
        results = cursor.fetchall()
        conn.close()
        return [r[0] for r in results]
    
    def get_all_industries(self, industry_type: str = 'sw') -> List[str]:
        """获取所有行业名称"""
        conn = self.get_connection()
        table = 'industry_sw' if industry_type == 'sw' else 'industry_citics'
        cursor = conn.cursor()
        cursor.execute(f"SELECT DISTINCT industry_name FROM {table} ORDER BY industry_name")
        results = cursor.fetchall()
        conn.close()
        return [r[0] for r in results]

