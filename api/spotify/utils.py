import re
import requests
from typing import Dict, Optional

class SpotifyUtils:
    """
    Utility class for analyzing Spotify Web Player and extracting credentials
    """
    
    @staticmethod
    def analyze_web_player_request(url: str) -> Dict:
        """
        Analyze a Spotify Web Player request to extract important parameters
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache',
            }
            
            response = requests.get(url, headers=headers)
            
            if response.status_code != 200:
                raise Exception(f"Failed to fetch web player: {response.status_code}")
            
            content = response.text
            
            # 尝试从多个位置提取token
            token_patterns = [
                r'accessToken:"([^"]+)"',  # 模式1
                r'"accessToken":"([^"]+)"', # 模式2
                r'access_token="([^"]+)"',  # 模式3
            ]
            
            for pattern in token_patterns:
                token_match = re.search(pattern, content)
                if token_match:
                    return {
                        "access_token": token_match.group(1),
                        "expires_in": 3600
                    }
            
            # 如果上述方法都失败，尝试获取客户端凭据
            client_id = "d8a5ed958d274c2e8ee717e6a4b0971d"  # Spotify Web Player 客户端ID
            token_url = "https://accounts.spotify.com/api/token"
            
            token_data = {
                'grant_type': 'client_credentials',
                'client_id': client_id,
            }
            
            token_response = requests.post(token_url, data=token_data)
            if token_response.status_code == 200:
                token_info = token_response.json()
                return {
                    "access_token": token_info["access_token"],
                    "expires_in": token_info.get("expires_in", 3600)
                }
            
            raise Exception("Failed to obtain access token")
            
        except Exception as e:
            raise Exception(f"Failed to get access token: {str(e)}")
    
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