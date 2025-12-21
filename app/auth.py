"""
认证和权限管理
"""
import uuid
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from fastapi import HTTPException, Request, Cookie
from app.database import Database
from app.permissions import ALL_PERMISSIONS


class AuthManager:
    def __init__(self, db: Database):
        self.db = db
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """验证密码"""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        except:
            return False
    
    def login(self, username: str, password: str) -> Dict:
        """用户登录"""
        user = self.db.get_user_by_username(username)
        if not user:
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        
        if not user['is_active']:
            raise HTTPException(status_code=403, detail="用户已被禁用")
        
        # 检查用户有效期
        if user['valid_until']:
            valid_until = datetime.strptime(user['valid_until'], '%Y%m%d%H%M%S')
            if valid_until < datetime.now():
                raise HTTPException(
                    status_code=403, 
                    detail="用户账号已过期，请联系管理员重新授权。管理员微信：yyongzf8"
                )
        
        if not self.verify_password(password, user['password_hash']):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        
        # 创建会话
        session_id = str(uuid.uuid4())
        
        # 获取会话时长（小时）
        session_duration_hours = int(self.db.get_system_config('session_duration_hours', '24'))
        expires_at = (datetime.now() + timedelta(hours=session_duration_hours)).strftime('%Y%m%d%H%M%S')
        
        self.db.create_session(user['id'], session_id, expires_at)
        
        # 获取用户权限
        if user['role'] == 'admin':
            permissions = ALL_PERMISSIONS
        else:
            permissions = self.db.get_user_permissions(user['id'])
        
        return {
            'session_id': session_id,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'role': user['role'],
                'permissions': permissions
            }
        }
    
    def logout(self, session_id: str):
        """用户登出"""
        self.db.delete_session(session_id)
    
    def get_current_user(self, session_id: Optional[str] = None) -> Optional[Dict]:
        """获取当前登录用户（包含权限信息）"""
        if not session_id:
            return None
        
        session = self.db.get_session(session_id)
        if not session:
            return None
        
        if not session['is_active']:
            self.db.delete_session(session_id)
            return None
        
        user_id = session['user_id']
        role = session['role']
        
        # 获取用户信息并检查有效期
        user = self.db.get_user_by_id(user_id)
        if not user:
            return None
        
        # 检查用户有效期
        if user['valid_until']:
            valid_until = datetime.strptime(user['valid_until'], '%Y%m%d%H%M%S')
            if valid_until < datetime.now():
                # 账号已过期，删除会话并返回过期信息
                self.db.delete_session(session_id)
                return {
                    'id': user_id,
                    'username': user['username'],
                    'role': role,
                    'expired': True,
                    'expired_message': '账号已过期，请联系管理员重新授权。管理员微信：yyongzf8'
                }
        
        # 获取用户权限
        if role == 'admin':
            # 管理员拥有所有权限
            permissions = ALL_PERMISSIONS
        else:
            permissions = self.db.get_user_permissions(user_id)
        
        return {
            'id': user_id,
            'username': session['username'],
            'role': role,
            'permissions': permissions
        }
    
    def require_auth(self, session_id: Optional[str] = None) -> Dict:
        """要求用户已登录"""
        user = self.get_current_user(session_id)
        if not user:
            raise HTTPException(status_code=401, detail="请先登录")
        return user
    
    def require_admin(self, session_id: Optional[str] = None) -> Dict:
        """要求管理员权限"""
        user = self.require_auth(session_id)
        if user['role'] != 'admin':
            raise HTTPException(status_code=403, detail="需要管理员权限")
        return user
    
    def require_permission(self, session_id: Optional[str] = None, permission_code: str = None) -> Dict:
        """要求指定权限"""
        user = self.require_auth(session_id)
        
        # 管理员始终拥有所有权限
        if user['role'] == 'admin':
            return user
        
        # 检查用户是否有指定权限
        if permission_code not in user.get('permissions', []):
            from app.permissions import get_permission_name
            permission_name = get_permission_name(permission_code)
            raise HTTPException(
                status_code=403, 
                detail=f"需要权限: {permission_name}"
            )
        
        return user

