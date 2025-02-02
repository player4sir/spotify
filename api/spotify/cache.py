from typing import Dict, Optional
import time
import json
from pathlib import Path
import os
import asyncpg
import random


class Cache:
    """文件缓存实现"""
    
    def __init__(self, cache_dir: str = ".cache", ttl: int = 3600):
        self.cache_dir = Path(cache_dir)
        self.ttl = ttl
        self.cache_dir.mkdir(exist_ok=True)
    
    def _get_cache_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{key}.json"
    
    async def get(self, key: str) -> Optional[Dict]:
        """获取缓存数据"""
        cache_path = self._get_cache_path(key)
        if not cache_path.exists():
            return None
            
        try:
            data = json.loads(cache_path.read_text())
            if time.time() - data["timestamp"] > self.ttl:
                cache_path.unlink()
                return None
            return data["value"]
        except:
            return None
    
    async def set(self, key: str, value: Dict):
        """设置缓存数据"""
        cache_path = self._get_cache_path(key)
        data = {
            "timestamp": time.time(),
            "value": value
        }
        cache_path.write_text(json.dumps(data))

class NeonCache:
    def __init__(self, ttl: int = 3600):
        self.ttl = ttl
        self.pool = None
        self._use_file_cache = False
        self._file_cache = None
        
    async def init(self):
        if self._use_file_cache:
            return
            
        if not self.pool:
            try:
                self.pool = await asyncpg.create_pool(
                    os.environ.get('DATABASE_URL'),
                    ssl='require'
                )
                
                # 创建缓存表
                async with self.pool.acquire() as conn:
                    await conn.execute('''
                        CREATE TABLE IF NOT EXISTS cache (
                            key TEXT PRIMARY KEY,
                            value JSONB,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            ttl INTEGER
                        )
                    ''')
                
                # 添加 token 表
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS spotify_token (
                        id INTEGER PRIMARY KEY DEFAULT 1,
                        access_token TEXT NOT NULL,
                        expires_at TIMESTAMP NOT NULL
                    )
                ''')
            except Exception as e:
                print(f"Failed to initialize Neon Cache: {e}")
                # 切换到文件缓存
                self._use_file_cache = True
                from .cache import Cache
                self._file_cache = Cache(
                    cache_dir=".cache",
                    ttl=self.ttl
                )
    
    async def get(self, key: str):
        await self.init()
        if self._use_file_cache:
            return await self._file_cache.get(key)
            
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    '''
                    SELECT value FROM cache 
                    WHERE key = $1 
                    AND created_at + (ttl || ' seconds')::interval > CURRENT_TIMESTAMP
                    ''', 
                    key
                )
                return row['value'] if row else None
        except Exception as e:
            print(f"Neon Cache get error: {e}")
            return None
    
    async def set(self, key: str, value: dict):
        await self.init()
        if self._use_file_cache:
            return await self._file_cache.set(key, value)
            
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    '''
                    INSERT INTO cache (key, value, ttl)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (key) DO UPDATE
                    SET value = $2, created_at = CURRENT_TIMESTAMP, ttl = $3
                    ''',
                    key, json.dumps(value), self.ttl
                )
        except Exception as e:
            print(f"Neon Cache set error: {e}")
    
    async def get_token(self) -> Optional[Dict]:
        """获取存储的token，支持轮换策略"""
        await self.init()
        try:
            async with self.pool.acquire() as conn:
                # 获取所有有效的token
                rows = await conn.fetch('''
                    SELECT access_token, 
                           EXTRACT(EPOCH FROM expires_at) as expires_at,
                           EXTRACT(EPOCH FROM created_at) as created_at
                    FROM spotify_token 
                    WHERE expires_at > CURRENT_TIMESTAMP
                    ORDER BY created_at DESC
                    LIMIT 3
                ''')
                
                if rows:
                    # 随机选择一个token，优先使用较新的token
                    weights = [3, 2, 1][:len(rows)]  # 较新的token权重更大
                    row = random.choices(rows, weights=weights, k=1)[0]
                    return {
                        "access_token": row["access_token"],
                        "expires_at": row["expires_at"]
                    }
        except Exception as e:
            print(f"Error getting token: {e}")
        return None
    
    async def set_token(self, token: str, expires_in: int):
        """存储token，保留最近的几个有效token"""
        await self.init()
        try:
            async with self.pool.acquire() as conn:
                # 插入新token
                await conn.execute('''
                    INSERT INTO spotify_token (access_token, expires_at, created_at)
                    VALUES ($1, 
                           CURRENT_TIMESTAMP + ($2 || ' seconds')::interval,
                           CURRENT_TIMESTAMP)
                ''', token, expires_in)
                
                # 清理过期和多余的token
                await conn.execute('''
                    DELETE FROM spotify_token 
                    WHERE id NOT IN (
                        SELECT id FROM spotify_token 
                        WHERE expires_at > CURRENT_TIMESTAMP 
                        ORDER BY created_at DESC 
                        LIMIT 3
                    )
                ''')
        except Exception as e:
            print(f"Error setting token: {e}") 