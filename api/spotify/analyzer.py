from typing import Dict, List
from .api import SpotifyAPI

class SpotifyAnalyzer:
    def __init__(self, api: SpotifyAPI):
        self.api = api

    async def analyze_artist(self, artist_id: str) -> Dict:
        """分析艺人的详细信息"""
        artist = await self.api.get_artist(artist_id)
        top_tracks = await self.api.get_artist_top_tracks(artist_id)
        
        # 计算平均流行度
        avg_popularity = sum(t['popularity'] for t in top_tracks['tracks']) / len(top_tracks['tracks'])
        
        return {
            "name": artist['name'],
            "followers": artist['followers']['total'],
            "genres": artist['genres'],
            "popularity": artist['popularity'],
            "avg_track_popularity": avg_popularity,
            "top_tracks": [
                {
                    "name": track['name'],
                    "popularity": track['popularity'],
                    "preview_url": track['preview_url'],
                    "external_url": track['external_urls']['spotify']
                }
                for track in top_tracks['tracks'][:10]
            ]
        }

    async def analyze_album(self, album_id: str) -> Dict:
        """分析专辑的详细信息"""
        album = await self.api.get_album(album_id)
        tracks = await self.api.get_album_tracks(album_id)
        
        return {
            "name": album['name'],
            "release_date": album['release_date'],
            "total_tracks": album['total_tracks'],
            "popularity": album.get('popularity', 0),
            "label": album.get('label', ''),
            "tracks": [
                {
                    "number": track['track_number'],
                    "name": track['name'],
                    "duration_ms": track['duration_ms'],
                    "preview_url": track['preview_url']
                }
                for track in tracks['items']
            ]
        }

    async def search_and_analyze(self, query: str) -> Dict:
        """搜索并分析结果"""
        results = await self.api.search(query, type="track,artist,album", limit=20)
        
        analysis = {
            "tracks": [],
            "artists": [],
            "albums": [],
            "statistics": {
                "popularity": {
                    "avg": 0,
                    "max": 0,
                    "min": 100
                },
                "genres": set(),
                "years": set()
            }
        }
        
        if "tracks" in results:
            for track in results['tracks']['items'][:5]:
                analysis['tracks'].append({
                    "name": track['name'],
                    "artist": track['artists'][0]['name'],
                    "popularity": track['popularity'],
                    "preview_url": track['preview_url']
                })
                
                # 更新统计数据
                pop = track['popularity']
                analysis['statistics']['popularity']['avg'] += pop
                analysis['statistics']['popularity']['max'] = max(
                    analysis['statistics']['popularity']['max'], 
                    pop
                )
                analysis['statistics']['popularity']['min'] = min(
                    analysis['statistics']['popularity']['min'], 
                    pop
                )
                
        if "artists" in results:
            for artist in results['artists']['items'][:3]:
                analysis['artists'].append({
                    "name": artist['name'],
                    "followers": artist['followers']['total'],
                    "genres": artist['genres'],
                    "popularity": artist['popularity']
                })
                analysis['statistics']['genres'].update(artist['genres'])
                
        if "albums" in results:
            for album in results['albums']['items'][:3]:
                analysis['albums'].append({
                    "name": album['name'],
                    "artist": album['artists'][0]['name'],
                    "release_date": album['release_date'],
                    "total_tracks": album['total_tracks']
                })
                if album.get('release_date'):
                    year = album['release_date'].split('-')[0]
                    analysis['statistics']['years'].add(year)
        
        # 计算平均流行度
        if analysis['tracks']:
            analysis['statistics']['popularity']['avg'] /= len(analysis['tracks'])
            
        # 转换集合为列表以便JSON序列化
        analysis['statistics']['genres'] = list(analysis['statistics']['genres'])
        analysis['statistics']['years'] = list(analysis['statistics']['years'])
        
        return analysis 