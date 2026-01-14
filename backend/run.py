import sys
from pathlib import Path

# Добавляем корневую папку в PYTHONPATH
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))


def main():
    try:
        from app.main import app
        import uvicorn

        print("🚀 Starting ТоварищБот API...")
        print("📍 Server: http://0.0.0.0:8000")
        print("📚 API Docs: http://0.0.0.0:8000/docs")
        print("⏹️  Press CTRL+C to stop")

        # Убираем reload для Windows
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True
        )

    except KeyboardInterrupt:
        print("\n👋 Server stopped")


if __name__ == "__main__":
    main()