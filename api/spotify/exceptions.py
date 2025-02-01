class SpotifyAPIError(Exception):
    """基础Spotify API异常"""
    def __init__(self, message, status_code=None, error_code=None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(self.message)

class TokenError(SpotifyAPIError):
    """Token相关错误"""
    pass

class RateLimitError(SpotifyAPIError):
    """请求频率限制错误"""
    pass

class ResourceNotFoundError(SpotifyAPIError):
    """资源不存在错误"""
    pass

class ValidationError(SpotifyAPIError):
    """参数验证错误"""
    pass

class MarketNotAvailableError(SpotifyAPIError):
    """市场不可用错误"""
    pass

class SearchResultEmptyError(SpotifyAPIError):
    """搜索结果为空错误"""
    pass 