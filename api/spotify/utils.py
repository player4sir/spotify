import re
import json
import requests
import time
import random
import httpx
import asyncio
from typing import Dict, Optional

class SpotifyUtils:
    """
    Utility class for analyzing Spotify Web Player and extracting credentials
    """
    
    # 定义多个客户端ID用于轮换
    CLIENT_IDS = [
        "d8a5ed958d274c2e8ee717e6a4b0971d",  # Web Player
        "4673445df7354f0aaa1de3523fa8b2f7",  # Mobile App
        "bff58e9698f94920b3c6a7c0623d94a5"   # Desktop App
    ]
    
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # 基础延迟秒数
    
    @staticmethod
    def _get_random_client_id() -> str:
        """随机获取一个客户端ID"""
        return random.choice(SpotifyUtils.CLIENT_IDS)
    
    @staticmethod
    async def analyze_web_player_request(url: str, retry_count: int = 0) -> Dict:
        """带重试机制的token获取"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
            
            # 使用 httpx 替代 requests 以支持异步
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)
                
                if response.status_code != 200:
                    raise Exception(f"Failed to fetch web player: {response.status_code}")
                
                content = response.text
                
                # 尝试多种方式获取token
                token = None
                
                # 方式1: 从script标签获取
                script_match = re.search(r'<script id="session".+?>\s*(.*?)\s*</script>', content, re.DOTALL)
                if script_match:
                    try:
                        session_data = json.loads(script_match.group(1))
                        if 'accessToken' in session_data:
                            token = session_data['accessToken']
                    except json.JSONDecodeError:
                        pass
                
                # 方式2: 正则匹配
                if not token:
                    token_patterns = [
                        r'accessToken:"([^"]+)"',
                        r'"accessToken":"([^"]+)"',
                        r'access_token="([^"]+)"'
                    ]
                    for pattern in token_patterns:
                        match = re.search(pattern, content)
                        if match:
                            token = match.group(1)
                            break
                
                # 方式3: 客户端凭据
                if not token:
                    client_id = SpotifyUtils._get_random_client_id()
                    token_url = "https://accounts.spotify.com/api/token"
                    token_data = {
                        'grant_type': 'client_credentials',
                        'client_id': client_id
                    }
                    token_response = await client.post(token_url, data=token_data)
                    if token_response.status_code == 200:
                        token_info = token_response.json()
                        token = token_info["access_token"]
                
                if token:
                    return {
                        "access_token": token,
                        "expires_in": 3600
                    }
                
                raise Exception("No token found")
                
        except Exception as e:
            if retry_count < SpotifyUtils.MAX_RETRIES:
                # 指数退避重试
                delay = SpotifyUtils.RETRY_DELAY * (2 ** retry_count) + random.uniform(0, 1)
                print(f"Retry {retry_count + 1}/{SpotifyUtils.MAX_RETRIES} after {delay:.2f}s")
                await asyncio.sleep(delay)  # 使用异步睡眠
                return await SpotifyUtils.analyze_web_player_request(url, retry_count + 1)
            raise Exception(f"Failed to get access token after {SpotifyUtils.MAX_RETRIES} retries: {str(e)}")
    
    @staticmethod
    def extract_token_from_headers(headers: Dict) -> Optional[str]:
        """
        Extract access token from request headers
        """
        auth_header = headers.get('authorization', '')
        if auth_header.startswith('Bearer '):
            return auth_header[7:]
        return None
    
    @staticmethod
    def analyze_api_response(response: Dict) -> Dict:
        """
        Analyze API response to extract useful information
        """
        result = {
            "endpoints": set(),
            "scopes": set(),
            "parameters": set()
        }
        
        print("\nAnalyzing API response...")
        
        def extract_urls(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if isinstance(value, str) and value.startswith('https://api.spotify.com'):
                        result["endpoints"].add(value)
                        print(f"Found endpoint: {value}")
                    extract_urls(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract_urls(item)
        
        try:
            extract_urls(response)
            print(f"Found {len(result['endpoints'])} unique endpoints")
        except Exception as e:
            print(f"Error analyzing response: {e}")
        
        return result 