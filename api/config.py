import os

# 环境配置
ENV_CONFIG = {
    "is_vercel": bool(os.environ.get('VERCEL')),
    "is_prod": bool(os.environ.get('VERCEL')),
    "database_url": os.environ.get('DATABASE_URL')
}

# API配置
API_CONFIG = {
    # 基础配置
    "base_url": "https://api.spotify.com/v1",
    "token_url": "https://accounts.spotify.com/api/token",
    
    # 市场配置
    "markets": {
        "default": "TW",
        "priority": ["TW", "HK", "SG", "MY", "CN", "US"]
    },
    
    # 缓存配置
    "cache": {
        "enabled": True,
        "type": "memory" if ENV_CONFIG["is_vercel"] else "file",
        "ttl": 3600
    }
}

# 搜索配置
SEARCH_CONFIG = {
    "default_limit": 20,
    "max_limit": 50,
    "types": ["track", "artist", "album", "playlist"]
} 