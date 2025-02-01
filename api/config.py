# API配置
import os


API_CONFIG = {
    # 基础配置
    "base_url": "https://api.spotify.com/v1",
    "token_url": "https://accounts.spotify.com/api/token",
    
    # 市场配置
    "markets": {
        "default": "TW",
        "priority": ["TW", "HK", "SG", "MY", "CN", "US"]
    },
    
    # Vercel KV 配置
    "cache": {
        "enabled": True,
        "type": "vercel_kv",
        "ttl": 3600
    }
}

# 搜索配置
SEARCH_CONFIG = {
    "default_limit": 20,
    "max_limit": 50,
    "types": ["track", "artist", "album", "playlist"]
} 