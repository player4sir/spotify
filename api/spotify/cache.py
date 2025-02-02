from typing import Dict, Optional
import time
import json
from pathlib import Path
import os
import asyncpg


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

class MemoryCache:
    """内存缓存实现"""
    _cache = {}
    
    def __init__(self, ttl: int = 3600):
        self.ttl = ttl
    
    async def get(self, key: str) -> Optional[Dict]:
        if key not in self._cache:
            return None
            
        data = self._cache[key]
        if time.time() - data["timestamp"] > self.ttl:
            del self._cache[key]
            return None
            
        return data["value"]
    
    async def set(self, key: str, value: Dict):
        self._cache[key] = {
            "timestamp": time.time(),
            "value": value
        } 