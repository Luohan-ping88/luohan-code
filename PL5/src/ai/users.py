"""用户管理模块
使用SQLite存储用户信息，使用bcrypt加密密码
"""

import os
import sqlite3
from typing import Dict, Optional, Tuple
import bcrypt

DATABASE_PATH = os.getenv("DATABASE_PATH", "data/users.db")


class UserManager:
    """用户管理器"""

    def __init__(self):
        self._init_database()

    def _init_database(self):
        """初始化数据库"""
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    token TEXT UNIQUE NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            conn.commit()

            # 初始化默认用户（仅在表为空时）
            cursor.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]
            if count == 0:
                self._create_default_users()

    def _create_default_users(self):
        """创建默认用户"""
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()

            # 创建admin用户
            admin_hash = bcrypt.hashpw("admin@123".encode(), bcrypt.gensalt())
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ("admin", admin_hash.decode(), "admin"),
            )

            # 创建user用户
            user_hash = bcrypt.hashpw("user@123".encode(), bcrypt.gensalt())
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ("user", user_hash.decode(), "user"),
            )

            # 创建guest用户
            guest_hash = bcrypt.hashpw("guest@123".encode(), bcrypt.gensalt())
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ("guest", guest_hash.decode(), "guest"),
            )

            conn.commit()

    def verify_password(
        self, username: str, password: str
    ) -> Tuple[bool, Optional[Dict]]:
        """验证用户密码

        Args:
            username: 用户名
            password: 密码

        Returns:
            (是否验证成功, 用户信息)
        """
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, password_hash, role FROM users WHERE username = ?",
                (username,),
            )
            row = cursor.fetchone()

            if row is None:
                return False, None

            user_id, username, password_hash, role = row

            if bcrypt.checkpw(password.encode(), password_hash.encode()):
                # 更新最后登录时间
                cursor.execute(
                    "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
                    (user_id,),
                )
                conn.commit()

                return True, {
                    "id": user_id,
                    "username": username,
                    "role": role,
                }

            return False, None

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """根据ID获取用户信息"""
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, role, created_at, last_login FROM users WHERE id = ?",
                (user_id,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            return {
                "id": row[0],
                "username": row[1],
                "role": row[2],
                "created_at": row[3],
                "last_login": row[4],
            }

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """根据用户名获取用户信息"""
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, role, created_at, last_login FROM users WHERE username = ?",
                (username,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            return {
                "id": row[0],
                "username": row[1],
                "role": row[2],
                "created_at": row[3],
                "last_login": row[4],
            }

    def create_user(
        self, username: str, password: str, role: str = "user"
    ) -> bool:
        """创建新用户"""
        try:
            password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

            with sqlite3.connect(DATABASE_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                    (username, password_hash.decode(), role),
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def update_user_role(self, username: str, role: str) -> bool:
        """更新用户角色"""
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET role = ? WHERE username = ?",
                (role, username),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_user(self, username: str) -> bool:
        """删除用户"""
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE username = ?", (username,))
            conn.commit()
            return cursor.rowcount > 0

    def list_users(self) -> list:
        """列出所有用户"""
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, username, role, created_at, last_login FROM users"
            )
            rows = cursor.fetchall()

            return [
                {
                    "id": row[0],
                    "username": row[1],
                    "role": row[2],
                    "created_at": row[3],
                    "last_login": row[4],
                }
                for row in rows
            ]

    def add_session(self, user_id: int, token: str, expires_at: int) -> bool:
        """添加用户会话"""
        try:
            with sqlite3.connect(DATABASE_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO user_sessions (user_id, token, expires_at) VALUES (?, ?, ?)",
                    (user_id, token, expires_at),
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def invalidate_session(self, token: str) -> bool:
        """使会话失效"""
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM user_sessions WHERE token = ?", (token,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def is_session_valid(self, token: str) -> bool:
        """检查会话是否有效"""
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM user_sessions WHERE token = ? AND expires_at > CURRENT_TIMESTAMP",
                (token,),
            )
            count = cursor.fetchone()[0]
            return count > 0


# 全局用户管理器实例
_user_manager = UserManager()


def get_user_manager() -> UserManager:
    """获取全局用户管理器"""
    return _user_manager
