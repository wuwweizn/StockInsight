"""
主程序入口（开发模式，支持自动重载）
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.api:app", host="0.0.0.0", port=8588, reload=True)

