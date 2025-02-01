from typing import Dict, Optional
import time
import json
from pathlib import Path
import os
import asyncpg


class Cache:
    """简单的文件缓存实现"""
    
    def __init__(self, cache_dir: str = ".cache", ttl: int = 3600):
        self.cache_dir = Path(cache_dir)
        self.ttl = ttl
        self.cache_dir.mkdir(exist_ok=True)
    
    def _get_cache_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{key}.json"
    
    def get(self, key: str) -> Optional[Dict]:
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
    
    def set(self, key: str, value: Dict):
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
        
    async def init(self):
        if not self.pool:
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
    
    async def get(self, key: str):
        await self.init()
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
    
    async def set(self, key: str, value: dict):
        await self.init()
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