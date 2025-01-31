import requests
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict
from enum import Enum
import logging  # 添加logging导入
import time
import re
import uuid
import urllib3
import os
import aiohttp
import asyncio

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = FastAPI(
    title="Spotify Web API",
    description="""
    非官方Spotify Web API，提供以下功能：
    
    * 🔍 搜索音乐、专辑、艺人
    * 🏠 获取首页数据（包含以下内容）：
        * 当红艺人
        * 热门专辑和单曲
        * 热门电台
        * 精选排行榜
        * State of music today
    * 📝 获取播放列表详情：
        * 基本信息（标题、描述、创建者等）
        * 歌曲列表（支持分页）
        * 封面图片
        * 统计信息（关注数、歌曲总数）
    
    所有数据来源于Spotify Web Player。
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 添加CORS支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ContentType(str, Enum):
    ALBUM = "album"
    PLAYLIST = "playlist"
    ARTIST = "artist"
    TRACK = "track"

class SpotifySearch:
    def __init__(self, max_retries: int = 3, verify_ssl: bool = False):
        """
        初始化Spotify搜索实例
        
        Args:
            max_retries: 最大重试次数
            verify_ssl: 是否验证SSL证书
        """
        self.verify_ssl = verify_ssl
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/132.0.0.0",
            "app-platform": "WebPlayer",
            "Origin": "https://open.spotify.com",
            "Referer": "https://open.spotify.com/",
        }
        
        # 创建session并配置
        self.session = requests.Session()
        
        # 设置重试策略
        retry_strategy = urllib3.Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = requests.adapters.HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # 配置SSL验证
        self.session.verify = self.verify_ssl
        
        # 获取client数据
        for i in range(max_retries):
            try:
                self.client_data = self._get_client_data()
                break
            except Exception as e:
                if i == max_retries - 1:
                    raise

    def _get_client_data(self) -> Dict:
        """从web-player.js中获取client相关数据"""
        try:
            # 1. 获取web-player.js的URL
            resp = self._make_request("GET", "https://open.spotify.com", headers=self.headers)
            
            # 提取web-player.js的URL
            js_url_match = re.search(r'<script src="(.*?web-player\.[a-zA-Z0-9]+\.js)"', resp.text)
            if not js_url_match:
                raise Exception("Could not find web-player.js URL")
            
            # 2. 获取web-player.js内容
            js_url = js_url_match.group(1)
            if not js_url.startswith('http'):
                js_url = f"https://open.spotify.com{js_url}"
            
            js_resp = self._make_request("GET", js_url, headers=self.headers)
            if js_resp.status_code != 200:
                raise Exception("Failed to fetch web-player.js")
            
            js_content = js_resp.text
            
            # 3. 提取关键参数
            # client_id
            client_id_match = re.search(r'clientId:"([a-zA-Z0-9]+)"', js_content)
            client_id = client_id_match.group(1) if client_id_match else "d8a5ed958d274c2e8ee717e6a4b0971d"
            
            # client_version
            version_match = re.search(r'version:"([^"]+)"', js_content)
            client_version = version_match.group(1) if version_match else "1.2.57.190"
            
            # 查询hash
            home_hash_match = re.search(r'home:\{hash:"([a-f0-9]+)"', js_content)
            home_hash = home_hash_match.group(1) if home_hash_match else "b3ef823f52e8e4c30e693ef24431b89760be10b429f2563ceaf169846dc5c4ab"
            
            browse_hash_match = re.search(r'browseView:\{hash:"([a-f0-9]+)"', js_content)
            browse_hash = browse_hash_match.group(1) if browse_hash_match else "0d2c2f09cb6c346aa7b01f86ab0f90007c3d9ea0ba11484a1639980e0939a192"
            
            search_hash_match = re.search(r'searchDesktop:\{hash:"([a-f0-9]+)"', js_content)
            search_hash = search_hash_match.group(1) if search_hash_match else "dd1513013a4ab0d9c095eac6b6d292c801bef038e11e06b746385a509be24ab0"
            
            return {
                "client_id": client_id,
                "client_version": client_version,
                "query_hashes": {
                    "home": home_hash,
                    "browse": browse_hash,
                    "search": search_hash
                }
            }
        except Exception:
            # 返回默认值
            return {
                "client_id": "d8a5ed958d274c2e8ee717e6a4b0971d",
                "client_version": "1.2.57.190",
                "query_hashes": {
                    "home": "b3ef823f52e8e4c30e693ef24431b89760be10b429f2563ceaf169846dc5c4ab",
                    "browse": "0d2c2f09cb6c346aa7b01f86ab0f90007c3d9ea0ba11484a1639980e0939a192",
                    "search": "dd1513013a4ab0d9c095eac6b6d292c801bef038e11e06b746385a509be24ab0"
                }
            }

    def _init_token(self):
        """初始化token和app版本"""
        try:
            # 1. 先获取app version
            resp = self._make_request("GET", "https://open.spotify.com", headers=self.headers)
            if resp.status_code == 200:
                config_match = re.search(r'<script id="config" data-config="([^"]+)"', resp.text)
                if config_match:
                    try:
                        config_data = json.loads(config_match.group(1).encode().decode('unicode-escape'))
                        self.headers["spotify-app-version"] = config_data.get("appVersion")
                    except Exception:
                        pass

                token_resp = self._make_request(
                    "GET",
                    "https://open.spotify.com/get_access_token?reason=transport&productType=web_player",
                    headers=self.headers
                )
                if token_resp.status_code == 200:
                    token_data = token_resp.json()
                    self.headers["authorization"] = f"Bearer {token_data.get('accessToken', '')}"
                    
                    client_token_payload = {
                        "client_data": {
                            "client_version": self.client_data["client_version"],
                            "client_id": self.client_data["client_id"],
                            "js_sdk_data": {
                                "device_brand": "unknown",
                                "device_model": "unknown",
                                "os": "windows",
                                "os_version": "NT 10.0",
                                "device_id": str(uuid.uuid4()).replace("-", ""),
                                "device_type": "computer"
                            }
                        }
                    }
                    
                    client_token_resp = self._make_request(
                        "POST",
                        "https://clienttoken.spotify.com/v1/clienttoken",
                        json=client_token_payload,
                        headers={
                            **self.headers,
                            "Content-Type": "application/json",
                            "Accept": "application/json"
                        }
                    )
                    
                    if client_token_resp.status_code == 200 and client_token_resp.text:
                        client_token_data = client_token_resp.json()                        
                        if client_token_data.get("response_type") == "RESPONSE_GRANTED_TOKEN_RESPONSE":
                            granted_token = client_token_data.get("granted_token", {})
                            self.headers["client-token"] = granted_token.get("token")
                            self.token_expires_after = granted_token.get("expires_after_seconds")
                            self.token_refresh_after = granted_token.get("refresh_after_seconds")
                            self.token_created_at = time.time()
        except Exception as e:
            raise

    def search(self, keyword: str, offset: int = 0, limit: int = 10) -> list:
        """搜索音乐
        Args:
            keyword: 搜索关键词
            offset: 起始位置
            limit: 返回结果数量
        Returns:
            包含歌曲信息的列表
        """
        resp = self._make_request(
            "GET",
            "https://api-partner.spotify.com/pathfinder/v1/query",
            params={
                "operationName": "searchDesktop",
                "variables": json.dumps({
                    "searchTerm": keyword,
                    "offset": offset,
                    "limit": limit,
                    "numberOfTopResults": 5,
                    "includeAudiobooks": True
                }),
                "extensions": json.dumps({
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": self.client_data["query_hashes"]["search"]
                    }
                })
            },
            headers=self.headers
        )
        
        if resp.status_code == 200:
            data = resp.json()
            if 'errors' in data:
                return []
                
            tracks = []
            for track in data.get('data', {}).get('searchV2', {}).get('tracksV2', {}).get('items', []):
                if track.get('item', {}).get('__typename') == 'TrackResponseWrapper':
                    track_data = track['item']['data']
                    if track_data.get('__typename') == 'Track':
                        # 获取最大尺寸的封面
                        cover_sources = track_data.get('albumOfTrack', {}).get('coverArt', {}).get('sources', [])
                        cover_url = max(cover_sources, key=lambda x: x.get('width', 0) or 0).get('url') if cover_sources else None
                        
                        tracks.append({
                            'name': track_data.get('name'),
                            'artists': [a['profile'].get('name') for a in track_data.get('artists', {}).get('items', [])],
                            'album': track_data.get('albumOfTrack', {}).get('name'),
                            'share_url': f"https://open.spotify.com/track/{track_data.get('id')}",
                            'cover_url': cover_url,
                            'duration_ms': track_data.get('duration', {}).get('totalMilliseconds')
                        })
            return tracks
        return []

    def _refresh_token_if_needed(self):
        """检查并刷新token如果需要"""
        try:
            current_time = time.time()
            # 检查是否需要刷新token
            if hasattr(self, 'token_created_at') and hasattr(self, 'token_refresh_after'):
                elapsed_time = current_time - self.token_created_at
                if elapsed_time > self.token_refresh_after:
                    self._init_token()
                    return
            
            # 测试当前token是否有效
            test_resp = self._make_request(
                "GET",
                "https://api-partner.spotify.com/pathfinder/v1/query",
                params={"operationName": "fetchPlaylistMetadata"},
                headers=self.headers
            )
            if test_resp.status_code == 401:
                self._init_token()
            
        except Exception as e:
            self._init_token()

    def get_home_data(self, limit: int = 10) -> Dict:
        """获取首页数据，包括当红艺人、热门专辑和单曲、热门电台、精选排行榜等"""
        try:
            self._refresh_token_if_needed()
            
            resp = self._make_request(
                "GET",
                "https://api-partner.spotify.com/pathfinder/v1/query",
                params={
                    "operationName": "home",
                    "variables": json.dumps({
                        "timeZone": "Asia/Shanghai",
                        "sp_t": "547485a859e1b1acac248586432c2799",
                        "facet": "",
                        "sectionItemsLimit": limit,
                        "enableDynamicColors": False
                    }),
                    "extensions": json.dumps({
                        "persistedQuery": {
                            "version": 1,
                            "sha256Hash": self.client_data["query_hashes"]["home"]
                        }
                    })
                },
                headers=self.headers
            )
            
            if resp.status_code == 200:
                data = resp.json()
                sections = data.get('data', {}).get('home', {}).get('sectionContainer', {}).get('sections', {}).get('items', [])
                
                result = {
                    'greeting': data.get('data', {}).get('home', {}).get('greeting', {}).get('transformedLabel'),
                    'sections': []
                }
                
                for section in sections:
                    section_data = {
                        'title': section.get('data', {}).get('title', {}).get('transformedLabel'),
                        'subtitle': section.get('data', {}).get('subtitle', {}).get('transformedLabel'),
                        'items': []
                    }
                    
                    items = section.get('sectionItems', {}).get('items', [])
                    for item in items:
                        content = item.get('content', {})
                        if not content:
                            continue
                            
                        item_data = content.get('data', {})
                        item_type = content.get('__typename')
                        
                        if item_type == 'ArtistResponseWrapper':
                            # 艺人
                            avatar_sources = item_data.get('visuals', {}).get('avatarImage', {}).get('sources', [])
                            avatar_url = avatar_sources[-1].get('url') if avatar_sources else None
                            
                            section_data['items'].append({
                                'type': 'artist',
                                'id': item_data.get('uri', '').split(':')[-1],
                                'name': item_data.get('profile', {}).get('name'),
                                'avatar_url': avatar_url,
                                'share_url': f"https://open.spotify.com/artist/{item_data.get('uri', '').split(':')[-1]}"
                            })
                        
                        elif item_type == 'AlbumResponseWrapper':
                            # 专辑
                            cover_sources = item_data.get('coverArt', {}).get('sources', [])
                            cover_url = cover_sources[-1].get('url') if cover_sources else None
                            
                            section_data['items'].append({
                                'type': 'album',
                                'id': item_data.get('uri', '').split(':')[-1],
                                'name': item_data.get('name'),
                                'artists': [a['profile'].get('name') for a in item_data.get('artists', {}).get('items', [])],
                                'cover_url': cover_url,
                                'album_type': item_data.get('albumType'),
                                'share_url': f"https://open.spotify.com/album/{item_data.get('uri', '').split(':')[-1]}"
                            })
                        
                        elif item_type == 'PlaylistResponseWrapper':
                            # 歌单/电台/排行榜
                            image_sources = item_data.get('images', {}).get('items', [{}])[0].get('sources', [])
                            image_url = image_sources[0].get('url') if image_sources else None
                            
                            section_data['items'].append({
                                'type': 'playlist',
                                'id': item_data.get('uri', '').split(':')[-1],
                                'name': item_data.get('name'),
                                'description': item_data.get('description'),
                                'cover_url': image_url,
                                'owner': item_data.get('ownerV2', {}).get('data', {}).get('name'),
                                'format': item_data.get('format'),  # chart为排行榜
                                'share_url': f"https://open.spotify.com/playlist/{item_data.get('uri', '').split(':')[-1]}"
                            })
                    
                    if section_data['items']:
                        result['sections'].append(section_data)
                
                return result
            else:
                return {'greeting': None, 'sections': []}
        except Exception as e:
            return {'greeting': None, 'sections': []}

    def get_playlist_tracks(self, playlist_id: str, offset: int = 0, limit: int = 100) -> Dict:
        """获取播放列表中的歌曲"""
        try:
            self._refresh_token_if_needed()
            
            resp = self._make_request(
                "GET", 
                "https://api-partner.spotify.com/pathfinder/v1/query",
                params={
                    "operationName": "fetchPlaylistContents",
                    "variables": json.dumps({
                        "uri": f"spotify:playlist:{playlist_id}",
                        "offset": offset,
                        "limit": limit
                    }),
                    "extensions": json.dumps({
                        "persistedQuery": {
                            "version": 1,
                            "sha256Hash": "2c2c2a14cfa3a338a68af8010f0b044aa0d06a696035689f977b0f228d243ffc"
                        }
                    })
                },
                headers=self.headers
            )
            
            if resp.status_code == 200:
                data = resp.json()
                logger.debug(f"Playlist response: {json.dumps(data, indent=2)}")
                
                playlist = data.get('data', {}).get('playlistV2', {})  # 改回 playlistV2
                content = playlist.get('content', {})  # 获取 content 字段
                
                # 获取播放列表基本信息
                result = {
                    'id': playlist_id,
                    'name': playlist.get('name'),
                    'description': playlist.get('description'),
                    'owner': playlist.get('ownerV2', {}).get('data', {}).get('name'),
                    'followers': playlist.get('followers', {}).get('total', 0),
                    'tracks_count': content.get('totalCount', 0),
                    'tracks': []
                }
                
                # 处理歌曲列表
                items = content.get('items', [])
                for item in items:
                    track_data = item.get('itemV2', {}).get('data', {})
                    if track_data.get('__typename') == 'Track':
                        # 获取最大尺寸的封面
                        cover_sources = track_data.get('albumOfTrack', {}).get('coverArt', {}).get('sources', [])
                        cover_url = max(cover_sources, key=lambda x: x.get('width', 0) or 0).get('url') if cover_sources else None
                        
                        result['tracks'].append({
                            'id': track_data.get('uri', '').split(':')[-1],
                            'name': track_data.get('name'),
                            'artists': [a['profile'].get('name') for a in track_data.get('artists', {}).get('items', [])],
                            'album': track_data.get('albumOfTrack', {}).get('name'),
                            'cover_url': cover_url,
                            'duration_ms': track_data.get('trackDuration', {}).get('totalMilliseconds'),
                            'share_url': f"https://open.spotify.com/track/{track_data.get('uri', '').split(':')[-1]}"
                        })
                
                return result
            return None
        except Exception as e:
            logger.error(f"Error getting playlist tracks: {str(e)}")
            return None

    async def get_album_tracks(self, album_id: str) -> Dict:
        """获取专辑中的歌曲"""
        try:
            self._refresh_token_if_needed()
            
            # 构造专辑详情请求
            params = {
                "operationName": "getAlbum",
                "variables": json.dumps({
                    "uri": f"spotify:album:{album_id}",
                    "locale": "",
                    "offset": 0,
                    "limit": 50
                }),
                "extensions": json.dumps({
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "8f4cd5650f9d80349dbe68684057476d8bf27a5c51687b2b1686099ab5631589"
                    }
                })
            }
            
            # 并行发送请求
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api-partner.spotify.com/pathfinder/v1/query",
                    params=params,
                    headers=self.headers,
                    ssl=False
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        album = data.get('data', {}).get('albumUnion', {})
                        
                        # 构造返回数据
                        result = {
                            'id': album_id,
                            'name': album.get('name'),
                            'type': album.get('type'),
                            'release_date': album.get('date', {}).get('isoString'),
                            'total_tracks': album.get('tracksV2', {}).get('totalCount', 0),
                            'artists': [{
                                'id': a.get('uri', '').split(':')[-1],
                                'name': a.get('profile', {}).get('name'),
                                'share_url': f"https://open.spotify.com/artist/{a.get('uri', '').split(':')[-1]}"
                            } for a in album.get('artists', {}).get('items', [])],
                            'tracks': []
                        }
                        
                        # 获取封面
                        cover_sources = album.get('coverArt', {}).get('sources', [])
                        if cover_sources:
                            result['cover_url'] = max(
                                cover_sources,
                                key=lambda x: x.get('width', 0) or 0
                            ).get('url')
                        
                        # 并行处理歌曲列表
                        tracks = album.get('tracksV2', {}).get('items', [])
                        async def process_track(item):
                            track_data = item.get('track')
                            if track_data:
                                artists = [{
                                    'id': a.get('uri', '').split(':')[-1],
                                    'name': a.get('profile', {}).get('name'),
                                    'share_url': f"https://open.spotify.com/artist/${a.get('uri', '').split(':').pop()}`"
                                } for a in track_data.get('artists', {}).get('items', [])]
                                
                                return {
                                    'id': track_data.get('uri', '').split(':')[-1],
                                    'name': track_data.get('name'),
                                    'track_number': track_data.get('trackNumber'),
                                    'disc_number': track_data.get('discNumber'),
                                    'duration_ms': track_data.get('duration', {}).get('totalMilliseconds'),
                                    'artists': artists,
                                    'playable': track_data.get('playability', {}).get('playable', False),
                                    'playcount': track_data.get('playcount'),
                                    'content_rating': track_data.get('contentRating', {}).get('label'),
                                    'share_url': f"https://open.spotify.com/track/${track_data.get('uri', '').split(':').pop()}`"
                                }
                            return None
                        
                        track_tasks = [process_track(item) for item in tracks]
                        result['tracks'] = [t for t in await asyncio.gather(*track_tasks) if t]
                        
                        # 添加额外信息
                        if album.get('label'):
                            result['label'] = album['label']
                        if album.get('copyright', {}).get('items'):
                            result['copyright'] = [c.get('text') for c in album['copyright']['items']]
                        if album.get('playability'):
                            result['playable'] = album['playability'].get('playable')
                        if album.get('sharingInfo'):
                            result['share_url'] = album['sharingInfo'].get('shareUrl')
                        
                        return result
                    return None
        except Exception as e:
            logger.error(f"Error getting album tracks: {str(e)}")
            return None

    def get_artist(self, artist_id: str) -> Dict:
        """获取艺人详情"""
        try:
            self._refresh_token_if_needed()
            
            resp = self._make_request(
                "GET",
                "https://api-partner.spotify.com/pathfinder/v1/query",
                params={
                    "operationName": "queryArtistOverview",
                    "variables": json.dumps({
                        "uri": f"spotify:artist:{artist_id}",
                        "locale": ""
                    }),
                    "extensions": json.dumps({
                        "persistedQuery": {
                            "version": 1,
                            "sha256Hash": "4bc52527bb77a5f8bbb9afe491e9aa725698d29ab73bff58d49169ee29800167"
                        }
                    })
                },
                headers=self.headers
            )
            
            if resp.status_code == 200:
                data = resp.json()
                logger.debug(f"Artist response: {json.dumps(data, indent=2)}")
                
                artist = data.get('data', {}).get('artistUnion', {})
                
                # 构造返回数据
                result = {
                    'id': artist_id,
                    'name': artist.get('profile', {}).get('name'),
                    'verified': artist.get('profile', {}).get('verified'),
                    'biography': artist.get('profile', {}).get('biography', {}).get('text'),
                    'monthly_listeners': artist.get('stats', {}).get('monthlyListeners'),
                    'followers': artist.get('stats', {}).get('followers'),
                    'world_rank': artist.get('stats', {}).get('worldRank'),
                    'genres': [g.get('name') for g in artist.get('profile', {}).get('genres', {}).get('items', [])],
                    'gallery': [],
                    'popular_tracks': [],
                    'albums': [],
                    'appears_on': [],
                    'related_artists': []
                }
                
                # 获取头像和封面图片
                visuals = artist.get('profile', {}).get('visuals', {})
                avatar_sources = visuals.get('avatarImage', {}).get('sources', [])
                if avatar_sources:
                    result['avatar_url'] = max(
                        avatar_sources,
                        key=lambda x: x.get('width', 0) or 0
                    ).get('url')
                
                header_sources = visuals.get('headerImage', {}).get('sources', [])
                if header_sources:
                    result['header_url'] = max(
                        header_sources,
                        key=lambda x: x.get('width', 0) or 0
                    ).get('url')
                
                # 获取画廊图片
                gallery = artist.get('profile', {}).get('visuals', {}).get('gallery', {}).get('items', [])
                for image in gallery:
                    sources = image.get('sources', [])
                    if sources:
                        result['gallery'].append(
                            max(sources, key=lambda x: x.get('width', 0) or 0).get('url')
                        )
                
                # 获取热门歌曲
                popular_tracks = artist.get('discography', {}).get('popularTracks', {}).get('items', [])
                for track in popular_tracks:
                    track_data = track.get('track')
                    if track_data:
                        # 获取封面
                        cover_sources = track_data.get('albumOfTrack', {}).get('coverArt', {}).get('sources', [])
                        cover_url = max(cover_sources, key=lambda x: x.get('width', 0) or 0).get('url') if cover_sources else None
                        
                        result['popular_tracks'].append({
                            'id': track_data.get('uri', '').split(':')[-1],
                            'name': track_data.get('name'),
                            'playcount': track_data.get('playcount'),
                            'duration_ms': track_data.get('duration', {}).get('totalMilliseconds'),
                            'album': track_data.get('albumOfTrack', {}).get('name'),
                            'cover_url': cover_url,
                            'share_url': f"https://open.spotify.com/track/{track_data.get('uri', '').split(':')[-1]}"
                        })
                
                # 获取专辑列表
                albums = artist.get('discography', {}).get('albums', {}).get('items', [])
                for album in albums:
                    album_data = album.get('releases', {}).get('items', [])[0]
                    if album_data:
                        # 获取封面
                        cover_sources = album_data.get('coverArt', {}).get('sources', [])
                        cover_url = max(cover_sources, key=lambda x: x.get('width', 0) or 0).get('url') if cover_sources else None
                        
                        result['albums'].append({
                            'id': album_data.get('uri', '').split(':')[-1],
                            'name': album_data.get('name'),
                            'type': album_data.get('type'),
                            'release_date': album_data.get('date', {}).get('isoString'),
                            'total_tracks': album_data.get('tracks', {}).get('totalCount'),
                            'cover_url': cover_url,
                            'share_url': f"https://open.spotify.com/album/{album_data.get('uri', '').split(':')[-1]}"
                        })
                
                # 获取合作歌曲
                appears = artist.get('discography', {}).get('appearsOn', {}).get('items', [])
                for appear in appears:
                    release_data = appear.get('releases', {}).get('items', [])[0]
                    if release_data:
                        # 获取封面
                        cover_sources = release_data.get('coverArt', {}).get('sources', [])
                        cover_url = max(cover_sources, key=lambda x: x.get('width', 0) or 0).get('url') if cover_sources else None
                        
                        result['appears_on'].append({
                            'id': release_data.get('uri', '').split(':')[-1],
                            'name': release_data.get('name'),
                            'type': release_data.get('type'),
                            'release_date': release_data.get('date', {}).get('isoString'),
                            'cover_url': cover_url,
                            'share_url': f"https://open.spotify.com/album/{release_data.get('uri', '').split(':')[-1]}"
                        })
                
                # 获取相关艺人
                related = artist.get('relatedContent', {}).get('relatedArtists', {}).get('items', [])
                for related_artist in related:
                    profile = related_artist.get('profile', {})
                    visuals = profile.get('visuals', {})
                    avatar_sources = visuals.get('avatarImage', {}).get('sources', [])
                    avatar_url = max(avatar_sources, key=lambda x: x.get('width', 0) or 0).get('url') if avatar_sources else None
                    
                    result['related_artists'].append({
                        'id': related_artist.get('uri', '').split(':')[-1],
                        'name': profile.get('name'),
                        'avatar_url': avatar_url,
                        'share_url': f"https://open.spotify.com/artist/{related_artist.get('uri', '').split(':')[-1]}"
                    })
                
                return result
            return None
        except Exception as e:
            logger.error(f"Error getting artist: {str(e)}")
            return None

    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """统一的请求方法，处理SSL验证"""
        try:
            # 添加超时设置
            kwargs['timeout'] = 10
            response = self.session.request(method, url, **kwargs)
            
            # 检查响应内容类型
            content_type = response.headers.get('content-type', '')
            if 'application/json' in content_type and response.content.strip():  # 确保响应不为空
                # 尝试解析JSON
                try:
                    response.json()
                except json.JSONDecodeError as e:
                    raise
            
            response.raise_for_status()
            return response
        except requests.exceptions.SSLError as e:
            # 如果SSL验证失败，尝试不验证SSL
            old_verify = self.session.verify
            self.session.verify = False
            try:
                response = self.session.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            finally:
                self.session.verify = old_verify
        except requests.exceptions.Timeout as e:
            raise
        except requests.exceptions.RequestException as e:
            raise

# 创建全局实例
try:
    spotify = SpotifySearch(verify_ssl=False)  # 默认不验证SSL
except Exception as e:
    raise

@app.get("/search")
async def search_track(
    q: str, 
    offset: int = 0, 
    limit: int = 10
):
    """Search Spotify tracks"""
    try:
        if limit > 50:
            limit = 50
        results = spotify.search(q, offset, limit)
        if not results:
            raise HTTPException(status_code=404, detail="No results found")
        return {
            "status": "success", 
            "data": results,
            "pagination": {
                "offset": offset,
                "limit": limit,
                "total": len(results)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/home")
async def get_home():
    """Get Spotify homepage data"""
    try:
        # 使用固定的limit值
        results = spotify.get_home_data(limit=10)  # 固定每个section返回10个items
        if not results['sections']:
            raise HTTPException(status_code=404, detail="No results found")
        return {
            "status": "success",
            "data": {
                "greeting": results['greeting'],
                "sections": results['sections']
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/playlist/{playlist_id}")
async def get_playlist(
    playlist_id: str,
    offset: int = 0,
    limit: int = 100
):
    """获取播放列表详情
    
    Args:
        playlist_id: 播放列表ID
        offset: 起始位置（默认0）
        limit: 返回歌曲数量（默认100，最大100）
    """
    try:
        if limit > 100:
            limit = 100
            
        result = spotify.get_playlist_tracks(playlist_id, offset, limit)
        if not result:
            raise HTTPException(status_code=404, detail="Playlist not found")
            
        return {
            "status": "success",
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/album/{album_id}")
async def get_album(
    album_id: str
):
    """获取专辑详情
    
    Args:
        album_id: 专辑ID
    """
    try:
        result = await spotify.get_album_tracks(album_id)
        if not result:
            raise HTTPException(status_code=404, detail="Album not found")
            
        return {
            "status": "success",
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/artist/{artist_id}")
async def get_artist_info(
    artist_id: str
):
    """获取艺人详情
    
    Args:
        artist_id: 艺人ID
    """
    try:
        result = spotify.get_artist(artist_id)
        if not result:
            raise HTTPException(status_code=404, detail="Artist not found")
            
        return {
            "status": "success",
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {"status": "ok", "message": "Spotify Search API is running"}

app = FastAPI()  # 确保这行在文件最后 