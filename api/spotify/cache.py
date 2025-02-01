from typing import Dict, Optional
import time
import json
from pathlib import Path
from vercel_kv import VercelKV


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

class VercelCache:
    def __init__(self, ttl: int = 3600):
        self.kv = VercelKV()
        self.ttl = ttl
    
    async def get(self, key: str):
        return await self.kv.get(key)
    
    async def set(self, key: str, value: dict):
        await self.kv.set(key, value, ex=self.ttl) 