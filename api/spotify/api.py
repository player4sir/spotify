from typing import Dict, List, Optional
import requests
from ..config import API_CONFIG, SEARCH_CONFIG
from .exceptions import *
from .cache import NeonCache
import hashlib
import os

class SpotifyAPI:
    """
    Spotify API wrapper based on discovered endpoints
    """
    def __init__(self, access_token: str, market: str = None):
        """初始化API客户端
        Args:
            access_token: Spotify访问令牌
            market: 市场代码
        """
        if not access_token:
            raise TokenError("Access token is required")
        
        # 如果token已经包含Bearer前缀，直接使用
        if access_token.startswith("Bearer "):
            token = access_token
        else:
            token = f"Bearer {access_token}"
        
        self.base_url = API_CONFIG["base_url"]
        self.market = market or API_CONFIG["markets"]["default"]
        self.headers = {
            "Authorization": token,
            "Content-Type": "application/json"
        }
        
        # Vercel环境检查
        is_vercel = os.environ.get('VERCEL')
        if is_vercel:
            # Vercel环境禁用缓存
            self.cache = None
        elif API_CONFIG["cache"]["enabled"]:
            self.cache = NeonCache(ttl=API_CONFIG["cache"]["ttl"])
    
    def search(
        self,
        query: str,
        type: str = "track",
        limit: int = None,
        offset: int = 0,
        market: str = None
    ) -> Dict:
        """搜索接口
        Args:
            query: 搜索关键词
            type: 搜索类型(track,artist,album,playlist)
            limit: 返回数量
            offset: 偏移量
            market: 市场代码
        """
        # 参数验证
        if type not in SEARCH_CONFIG["types"]:
            raise ValidationError(f"Invalid search type: {type}")
            
        limit = min(
            limit or SEARCH_CONFIG["default_limit"],
            SEARCH_CONFIG["max_limit"]
        )
        
        params = {
            "q": query,
            "type": type,
            "limit": limit,
            "offset": offset
        }
        
        # 只在提供 market 参数时添加
        if market:
            params["market"] = market
        elif self.market:
            params["market"] = self.market
        
        return self._get("/search", params)
    
    def get_playlist(self, playlist_id: str) -> Dict:
        """获取播放列表信息"""
        return self._get(f"/playlists/{playlist_id}")
    
    def get_playlist_tracks(self, playlist_id: str, limit: int = 20, offset: int = 0) -> Dict:
        """获取播放列表中的歌曲"""
        params = {
            "limit": limit,
            "offset": offset
        }
        return self._get(f"/playlists/{playlist_id}/tracks", params)
    
    def get_artist(self, artist_id: str) -> Dict:
        """获取艺人信息"""
        if not artist_id:
            raise ValidationError("Artist ID is required")
        return self._get(f"/artists/{artist_id}")
    
    def get_artist_albums(self, artist_id: str, album_type: str = None, limit: int = 20) -> Dict:
        """获取艺人的专辑列表"""
        params = {"limit": limit}
        if album_type:
            params["include_groups"] = album_type
        return self._get(f"/artists/{artist_id}/albums", params)
    
    def get_artist_top_tracks(self, artist_id: str, market: str = None) -> Dict:
        """获取艺人热门歌曲"""
        params = {"market": market or self.market}
        return self._get(f"/artists/{artist_id}/top-tracks", params)
    
    def get_related_artists(self, artist_id: str) -> Dict:
        """获取相关艺人"""
        return self._get(f"/artists/{artist_id}/related-artists")
    
    def get_album(self, album_id: str, market: str = None) -> Dict:
        """获取专辑信息"""
        params = {"market": market or self.market} if market or self.market else None
        return self._get(f"/albums/{album_id}", params)
    
    def get_album_tracks(self, album_id: str, limit: int = 20, offset: int = 0) -> Dict:
        """获取专辑歌曲列表"""
        params = {
            "limit": limit,
            "offset": offset
        }
        return self._get(f"/albums/{album_id}/tracks", params)
    
    def get_track(self, track_id: str, market: str = None) -> Dict:
        """获取歌曲信息"""
        params = {"market": market or self.market} if market or self.market else None
        return self._get(f"/tracks/{track_id}", params)
    
    def get_several_tracks(self, track_ids: List[str]) -> Dict:
        """批量获取歌曲信息"""
        return self._get("/tracks", {"ids": ",".join(track_ids)})
    
    def get_audio_features(self, track_id: str) -> Dict:
        """获取歌曲音频特征"""
        return self._get(f"/audio-features/{track_id}")
    
    def get_user_profile(self, user_id: str) -> Dict:
        """获取用户信息"""
        return self._get(f"/users/{user_id}")
    
    def get_current_user_playlists(self, limit: int = 20, offset: int = 0) -> Dict:
        """获取当前用户的播放列表"""
        params = {
            "limit": limit,
            "offset": offset
        }
        return self._get("/me/playlists", params)
    
    def get_new_releases(self, limit: int = 20, offset: int = 0, market: str = None) -> Dict:
        """获取新发行专辑"""
        params = {
            "limit": limit,
            "offset": offset,
            "market": market or self.market
        }
        return self._get("/browse/new-releases", params)
    
    def get_featured_playlists(self, limit: int = 20, offset: int = 0, market: str = None) -> Dict:
        """获取推荐歌单"""
        params = {
            "limit": limit,
            "offset": offset,
            "market": market or self.market
        }
        return self._get("/browse/featured-playlists", params)
    
    def get_categories(self, limit: int = 20, offset: int = 0, market: str = None) -> Dict:
        """获取音乐分类"""
        params = {
            "limit": limit,
            "offset": offset,
            "market": market or self.market
        }
        return self._get("/browse/categories", params)
    
    def get_category_playlists(
        self,
        category_id: str,
        limit: int = 20,
        offset: int = 0,
        market: str = None
    ) -> Dict:
        """获取分类下的歌单"""
        params = {
            "limit": limit,
            "offset": offset,
            "market": market or self.market
        }
        return self._get(f"/browse/categories/{category_id}/playlists", params)
    
    def get_several_artists(self, artist_ids: List[str]) -> Dict:
        """批量获取艺人信息"""
        return self._get("/artists", {"ids": ",".join(artist_ids)})
    
    def get_recommendations(
        self,
        seed_artists: List[str] = None,
        seed_tracks: List[str] = None,
        seed_genres: List[str] = None,
        limit: int = 20,
        market: str = None,
        **kwargs
    ) -> Dict:
        """获取推荐歌曲"""
        params = {
            "limit": limit,
            "market": market or self.market
        }
        
        if seed_artists:
            params["seed_artists"] = ",".join(seed_artists)
        if seed_tracks:
            params["seed_tracks"] = ",".join(seed_tracks)
        if seed_genres:
            params["seed_genres"] = ",".join(seed_genres)
            
        params.update(kwargs)
        return self._get("/recommendations", params)
    
    async def _get(self, endpoint: str, params: Dict = None) -> Dict:
        """请求处理"""
        url = f"{self.base_url}{endpoint}"
        
        cache_key = self._generate_cache_key(url, params)
        if hasattr(self, 'cache'):
            cached = await self.cache.get(cache_key)
            if cached:
                return cached
        
        try:
            # 先检查token格式
            if not self.headers.get("Authorization", "").startswith("Bearer "):
                raise TokenError("Invalid token format")
            
            response = requests.get(url, headers=self.headers, params=params)
            
            # 检查token相关错误
            if response.status_code == 401:
                raise TokenError("Invalid or expired token")
            
            # 其他错误处理
            try:
                error_data = response.json()
                error = error_data.get('error', {})
                error_message = error.get('message', '')
                error_status = error.get('status', response.status_code)
                
                if error_status == 404:
                    raise ResourceNotFoundError(f"Resource not found: {endpoint}")
                elif error_status == 429:
                    raise RateLimitError("Too many requests")
                elif error_status == 400:
                    if "invalid id" in error_message.lower():
                        raise ResourceNotFoundError(f"Invalid ID: {endpoint}")
                    else:
                        raise ValidationError(error_message or "Invalid request")
            except (ValueError, KeyError):
                # 如果无法解析JSON，使用原始状态码
                if response.status_code == 404:
                    raise ResourceNotFoundError(f"Resource not found: {endpoint}")
                elif response.status_code == 429:
                    raise RateLimitError("Too many requests")
                elif response.status_code == 400:
                    raise ValidationError("Invalid request")
            
            response.raise_for_status()
            data = response.json()
            
            if hasattr(self, 'cache'):
                await self.cache.set(cache_key, data)
                
            return data
            
        except requests.exceptions.RequestException as e:
            # 网络错误或其他请求异常
            if isinstance(e, requests.exceptions.HTTPError):
                if e.response.status_code == 401:
                    raise TokenError("Invalid or expired token")
                elif e.response.status_code == 404:
                    raise ResourceNotFoundError(f"Resource not found: {endpoint}")
                elif e.response.status_code == 429:
                    raise RateLimitError("Too many requests")
                elif e.response.status_code == 400:
                    raise ValidationError("Invalid request")
            raise SpotifyAPIError(f"Request failed: {str(e)}")

    def _post(self, endpoint: str, data: Dict = None) -> Dict:
        """通用POST请求方法"""
        response = requests.post(
            f"{self.base_url}{endpoint}",
            headers=self.headers,
            json=data
        )
        response.raise_for_status()
        return response.json()

    def _get_all_items(self, 
                      endpoint: str, 
                      params: Dict = None, 
                      key: str = "items") -> List:
        """获取分页接口的所有数据"""
        if params is None:
            params = {}
        
        items = []
        offset = 0
        limit = params.get("limit", 20)
        
        while True:
            params["offset"] = offset
            response = self._get(endpoint, params)
            
            if key not in response:
                break
                
            batch = response[key]
            if not batch:
                break
                
            items.extend(batch)
            offset += limit
            
            if "next" not in response or not response["next"]:
                break
        
        return items 

    def _get_best_market(self) -> str:
        """获取最佳可用市场"""
        for market in API_CONFIG["markets"]["priority"]:
            try:
                results = self.search("周杰伦", type="track", limit=1, market=market)
                if results.get("tracks", {}).get("items"):
                    return market
            except:
                continue
        return "US"  # 默认回退到US市场 

    def _generate_cache_key(self, url: str, params: Dict = None) -> str:
        """生成缓存key"""
        if params is None:
            params = {}
        return hashlib.md5(
            f"{self.market}:{url}:{str(sorted(params.items()) if params else '')}".encode()
        ).hexdigest()