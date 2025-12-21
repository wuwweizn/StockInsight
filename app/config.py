"""
配置管理
"""
import os
import json
from typing import Dict, Optional


class Config:
    def __init__(self, config_file: str = None):
        # 支持环境变量指定配置文件路径（用于Docker部署）
        if config_file is None:
            import os
            config_file = os.getenv("CONFIG_PATH", "config.json")
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self) -> Dict:
        """加载配置"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return self.get_default_config()
    
    def get_default_config(self) -> Dict:
        """默认配置"""
        return {
            "data_source": "akshare",
            "tushare": {
                "token": ""
            },
            "baostock": {},
            "finnhub": {
                "api_key": ""
            },
            "akshare": {},
            "update_frequency": "monthly"
        }
    
    def save_config(self):
        """保存配置"""
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
    
    def get(self, key: str, default=None):
        """获取配置值"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def set(self, key: str, value):
        """设置配置值"""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self.save_config()
    
    def get_data_source_config(self) -> Dict:
        """获取当前数据源配置"""
        data_source = self.get('data_source', 'tushare')
        return self.get(data_source, {})

