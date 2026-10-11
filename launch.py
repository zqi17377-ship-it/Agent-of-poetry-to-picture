"""Run the local studio with one command."""
import argparse
import threading
import webbrowser
from pathlib import Path
import uvicorn
from backend.app.main import create_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not (Path(__file__).parent / "frontend" / "dist" / "index.html").exists():
        raise SystemExit("请先运行 安装依赖.cmd，或在 frontend 目录执行 npm run build。")
    url = f"http://127.0.0.1:{args.port}"
    print(f"余境已启动：{url}\n按 Ctrl+C 停止应用。", flush=True)
    if not args.no_browser:
        timer = threading.Timer(1.5, webbrowser.open, args=(url,))
        timer.daemon = True
        timer.start()
    uvicorn.run(create_app(), host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
