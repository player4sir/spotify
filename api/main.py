from fastapi import FastAPI, HTTPException, Depends, Header, Query, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List
from pydantic import BaseModel, Field
from api.spotify.analyzer import SpotifyAnalyzer
from api.spotify.api import SpotifyAPI
from api.spotify.utils import SpotifyUtils
from api.spotify.exceptions import *
from datetime import datetime, timedelta

# 创建FastAPI应用
app = FastAPI(
    title="Spotify API",
    description="Spotify Web API 增强版接口",
    version="1.0.0",
    root_path=""  # 确保根路径正确
)

# 安全认证方案
security = HTTPBearer(auto_error=False)

# 请求/响应模型
class TokenResponse(BaseModel):
    access_token: str = Field(..., description="访问令牌")
    expires_in: int = Field(3600, description="过期时间(秒)")

class SearchParams(BaseModel):
    q: str = Field(..., description="搜索关键词")
    type: str = Field("track", description="搜索类型: track/artist/album")
    limit: int = Field(20, ge=1, le=50, description="返回数量")
    offset: int = Field(0, ge=0, description="偏移量")
    market: Optional[str] = Field(None, description="市场代码")

class ErrorDetail(BaseModel):
    code: str = Field(..., description="错误代码")
    message: str = Field(..., description="错误信息")

class ErrorResponse(BaseModel):
    error: ErrorDetail

# 添加一个全局 token 缓存
class TokenCache:
    def __init__(self):
        self.token = None
        self.expires_at = None
    
    def set(self, token: str, expires_in: int):
        self.token = token
        self.expires_at = datetime.now() + timedelta(seconds=expires_in)
    
    def get(self) -> Optional[str]:
        if not self.token or not self.expires_at:
            return None
        if datetime.now() >= self.expires_at:
            return None
        return self.token

token_cache = TokenCache()

# 修改 get_spotify 依赖
async def get_spotify(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> SpotifyAPI:
    try:
        if credentials:
            # 如果请求中提供了token，优先使用
            return SpotifyAPI(credentials.credentials)
        
        # 尝试使用缓存的token
        cached_token = token_cache.get()
        if cached_token:
            return SpotifyAPI(cached_token)
        
        # 缓存失效，重新获取token
        token_info = SpotifyUtils.analyze_web_player_request("https://open.spotify.com")
        if not token_info or "access_token" not in token_info:
            raise Exception("Failed to get access token")
            
        token_cache.set(
            token_info["access_token"], 
            token_info.get("expires_in", 3600)
        )
        return SpotifyAPI(token_info["access_token"])
        
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail={"code": "TOKEN_ERROR", "message": str(e)}
        )

# 修改 token 接口
@app.get(
    "/api/token", 
    response_model=TokenResponse,
    summary="获取访问令牌",
    description="获取或刷新访问令牌"
)
async def get_token():
    try:
        # 先尝试使用缓存的token
        cached_token = token_cache.get()
        if cached_token:
            return {
                "access_token": cached_token,
                "expires_in": int((token_cache.expires_at - datetime.now()).total_seconds())
            }
        
        # 缓存失效，重新获取
        token_info = SpotifyUtils.analyze_web_player_request("https://open.spotify.com")
        if not token_info or "access_token" not in token_info:
            raise Exception("Failed to get access token")
            
        token_cache.set(
            token_info["access_token"], 
            token_info.get("expires_in", 3600)
        )
        
        return {
            "access_token": token_info["access_token"],
            "expires_in": token_info.get("expires_in", 3600)
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "TOKEN_ERROR", "message": str(e)}
        )

@app.get("/api/search")
async def search(
    q: str = Query(..., description="搜索关键词"),
    type: str = Query("track", description="搜索类型"),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    spotify: SpotifyAPI = Depends(get_spotify)
):
    """搜索接口"""
    try:
        return await spotify.search(query=q, type=type, limit=limit, offset=offset)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/artist/{artist_id}")
async def get_artist(artist_id: str, spotify: SpotifyAPI = Depends(get_spotify)):
    """获取艺人信息"""
    try:
        return await spotify.get_artist(artist_id)
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"code": "ARTIST_NOT_FOUND", "message": f"Artist {artist_id} not found"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "ARTIST_ERROR", "message": str(e)}
        )

@app.get("/api/artist/{artist_id}/albums")
async def get_artist_albums(
    artist_id: str, 
    album_type: str = None,
    limit: int = 20,
    spotify: SpotifyAPI = Depends(get_spotify)
):
    """获取艺人专辑列表"""
    try:
        return await spotify.get_artist_albums(artist_id, album_type=album_type, limit=limit)
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"code": "ARTIST_NOT_FOUND", "message": f"Artist {artist_id} not found"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "ARTIST_ALBUMS_ERROR", "message": str(e)}
        )

@app.get("/api/artist/{artist_id}/top-tracks")
async def get_artist_top_tracks(
    artist_id: str,
    market: str = None,
    spotify: SpotifyAPI = Depends(get_spotify)
):
    """获取艺人热门歌曲"""
    try:
        return await spotify.get_artist_top_tracks(artist_id, market=market)
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"code": "ARTIST_NOT_FOUND", "message": f"Artist {artist_id} not found"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "TOP_TRACKS_ERROR", "message": str(e)}
        )

@app.get("/api/artist/{artist_id}/related")
async def get_related_artists(artist_id: str, spotify: SpotifyAPI = Depends(get_spotify)):
    """获取相关艺人"""
    return await spotify.get_related_artists(artist_id)

@app.get("/api/album/{album_id}")
async def get_album(
    album_id: str,
    market: str = None,
    spotify: SpotifyAPI = Depends(get_spotify)
):
    """获取专辑信息"""
    try:
        return await spotify.get_album(album_id, market=market)
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"code": "ALBUM_NOT_FOUND", "message": f"Album {album_id} not found"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "ALBUM_ERROR", "message": str(e)}
        )

@app.get("/api/album/{album_id}/tracks")
async def get_album_tracks(
    album_id: str,
    limit: int = 20,
    offset: int = 0,
    spotify: SpotifyAPI = Depends(get_spotify)
):
    """获取专辑曲目"""
    try:
        return await spotify.get_album_tracks(album_id, limit=limit, offset=offset)
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"code": "ALBUM_NOT_FOUND", "message": f"Album {album_id} not found"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "ALBUM_TRACKS_ERROR", "message": str(e)}
        )

@app.get("/api/track/{track_id}")
async def get_track(
    track_id: str,
    market: str = None,
    spotify: SpotifyAPI = Depends(get_spotify)
):
    """获取歌曲信息"""
    try:
        return await spotify.get_track(track_id, market=market)
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"code": "TRACK_NOT_FOUND", "message": f"Track {track_id} not found"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "TRACK_ERROR", "message": str(e)}
        )

@app.get("/api/tracks")
async def get_several_tracks(
    ids: str = Query(..., description="歌曲ID列表，用逗号分隔"),
    spotify: SpotifyAPI = Depends(get_spotify)
):
    """批量获取歌曲信息"""
    track_ids = ids.split(',')
    return await spotify.get_several_tracks(track_ids)

@app.get("/api/track/{track_id}/audio-features")
async def get_audio_features(track_id: str, spotify: SpotifyAPI = Depends(get_spotify)):
    """获取歌曲音频特征"""
    return await spotify.get_audio_features(track_id)

@app.get("/api/playlist/{playlist_id}")
async def get_playlist(playlist_id: str, spotify: SpotifyAPI = Depends(get_spotify)):
    """获取播放列表信息"""
    return await spotify.get_playlist(playlist_id)

@app.get("/api/playlist/{playlist_id}/tracks")
async def get_playlist_tracks(
    playlist_id: str,
    limit: int = 20,
    offset: int = 0,
    spotify: SpotifyAPI = Depends(get_spotify)
):
    """获取播放列表曲目"""
    return await spotify.get_playlist_tracks(playlist_id, limit=limit, offset=offset)

@app.get("/api/analyze")
async def analyze_search(
    q: str = Query(..., description="搜索关键词"),
    spotify: SpotifyAPI = Depends(get_spotify)
):
    """综合分析搜索结果"""
    analyzer = SpotifyAnalyzer(spotify)
    return await analyzer.search_and_analyze(q)

# 首页相关接口
@app.get("/api/featured")
async def get_featured(spotify: SpotifyAPI = Depends(get_spotify)):
    """获取首页推荐内容"""
    try:
        featured = {
            "top_artists": await spotify.get_several_artists([
                "0BezPR1Hn38i8qShQKunSD",  # 周杰伦
                "6gvSKE72vF6N20LfBqrDmm",  # 林俊杰
                "1cg0bYpP5e2DNG0RgK2CMN",  # 薛之谦
                "2QcZxAgcs2I1q7CtCkl6MI",   # 陈奕迅
                "7aRC4L63dBn3CiLDuWaLSI",
                "3df3XLKuqTQ6iOSmi0K3Wp",
                "0mG77q0N7TRltkLh4p2ASD",
                "0Riv2KnFcLZA3JSVryRg4y"
            ]),
            "hot_albums": await spotify.get_new_releases(
                limit=10,
                market=spotify.market
            ),
            "hot_tracks": await spotify.get_recommendations(
                seed_artists=["0BezPR1Hn38i8qShQKunSD","0Riv2KnFcLZA3JSVryRg4y","1cg0bYpP5e2DNG0RgK2CMN"],
                limit=10,
                market=spotify.market
            ),
            "featured_playlists": await spotify.get_featured_playlists(
                limit=6,
                market=spotify.market
            ),
            "charts": await spotify.get_category_playlists(
                category_id="toplists",
                limit=5,
                market=spotify.market
            )
        }
        return featured
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "FEATURED_ERROR", "message": str(e)}
        )

@app.get("/api/new-releases")
async def get_new_releases(
    limit: int = 20,
    offset: int = 0,
    spotify: SpotifyAPI = Depends(get_spotify)
):
    """获取新发行专辑"""
    try:
        return await spotify.get_new_releases(
            limit=limit,
            offset=offset,
            market=spotify.market
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "NEW_RELEASES_ERROR", "message": str(e)}
        )

@app.get("/api/categories")
async def get_categories(
    limit: int = 20,
    offset: int = 0,
    spotify: SpotifyAPI = Depends(get_spotify)
):
    """获取音乐分类"""
    try:
        return await spotify.get_categories(
            limit=limit,
            offset=offset,
            market=spotify.market
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "CATEGORIES_ERROR", "message": str(e)}
        )

@app.get("/api/category/{category_id}/playlists")
async def get_category_playlists(
    category_id: str,
    limit: int = 20,
    offset: int = 0,
    spotify: SpotifyAPI = Depends(get_spotify)
):
    """获取分类下的歌单"""
    try:
        return await spotify.get_category_playlists(
            category_id=category_id,
            limit=limit,
            offset=offset,
            market=spotify.market
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": "CATEGORY_PLAYLISTS_ERROR", "message": str(e)}
        )

# 添加CORS中间件
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头部
) 
