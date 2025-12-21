"""
生产环境启动脚本（不使用自动重载）
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.api:app",
        host="0.0.0.0",
        port=8588,
        reload=False,
        workers=1
    )

