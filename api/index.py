from spotify_search import app

# Export the FastAPI app for Vercel serverless function
def handler(request, context):
    return app(request, context)

# 这个文件作为Vercel的入口点 