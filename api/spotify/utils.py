import re
import json
import requests
from typing import Dict, Optional
from urllib.parse import urlparse, parse_qs
import logging

class SpotifyUtils:
    """
    Utility class for analyzing Spotify Web Player and extracting credentials
    """
    
    @staticmethod
    def analyze_web_player_request(url: str) -> Dict:
        """
        Analyze a Spotify Web Player request to extract important parameters
        """
        print(f"Analyzing Web Player at URL: {url}")
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
            
            print("Sending request to Spotify Web Player...")
            response = requests.get(url, headers=headers)
            print(f"Response status code: {response.status_code}")
            
            if response.status_code != 200:
                print(f"Error: Received status code {response.status_code}")
                return {"error": f"Failed to fetch web player: {response.status_code}"}
            
            content = response.text
            print(f"Received content length: {len(content)} characters")
            
            # 尝试从script标签中提取JSON数据
            script_pattern = r'<script id="session".+?>\s*(.*?)\s*</script>'
            script_match = re.search(script_pattern, content, re.DOTALL)
            if script_match:
                try:
                    session_data = json.loads(script_match.group(1))
                    print("Found session data in script tag")
                    if 'accessToken' in session_data:
                        return {"access_token": session_data['accessToken']}
                except json.JSONDecodeError:
                    print("Warning: Failed to parse session data JSON")
            
            # 如果上面的方法失败，尝试正则匹配
            token_match = re.search(r'accessToken:"([^"]+)"', content)
            if token_match:
                return {"access_token": token_match.group(1)}
            
            return {"error": "No access token found"}
            
        except requests.RequestException as e:
            print(f"Network error occurred: {e}")
            return {"error": str(e)}
        except Exception as e:
            print(f"Unexpected error occurred: {e}")
            return {"error": str(e)}
    
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