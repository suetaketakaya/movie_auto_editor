"""
Setup Test Script
システムの依存関係とセットアップをテストする
"""

import sys
import subprocess
import importlib
import requests

# Windows環境でのUnicode出力設定
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def test_python_version():
    """Pythonバージョンチェック"""
    print("[*] Testing Python version...")
    version = sys.version_info
    print(f"  Python {version.major}.{version.minor}.{version.micro}")

    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print("  [FAIL] Python 3.10以上が必要です")
        return False

    print("  [OK] Python version OK")
    return True


def test_package_imports():
    """必要なPythonパッケージのインポートテスト"""
    print("\n[*] Testing Python packages...")

    packages = {
        "fastapi": "FastAPI",
        "uvicorn": "Uvicorn",
        "cv2": "OpenCV",
        "yaml": "PyYAML",
        "requests": "Requests",
        "PIL": "Pillow"
    }

    all_ok = True
    for package, name in packages.items():
        try:
            importlib.import_module(package)
            print(f"  [OK] {name}")
        except ImportError:
            print(f"  [FAIL] {name} not installed")
            all_ok = False

    return all_ok


def test_ffmpeg():
    """FFmpegのインストールチェック"""
    print("\n[*] Testing FFmpeg...")
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:
            # バージョン情報から最初の行を取得
            version_line = result.stdout.split('\n')[0]
            print(f"  {version_line}")
            print("  [OK] FFmpeg OK")
            return True
        else:
            print("  [FAIL] FFmpeg not working")
            return False

    except FileNotFoundError:
        print("  [FAIL] FFmpeg not found in PATH")
        print("  Please install FFmpeg: https://ffmpeg.org/download.html")
        return False
    except Exception as e:
        print(f"  [FAIL] FFmpeg test failed: {e}")
        return False


def test_ollama():
    """Ollama接続テスト"""
    print("\n[*] Testing Ollama connection...")

    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)

        if response.status_code == 200:
            data = response.json()
            models = data.get("models", [])

            print(f"  [OK] Ollama server running")
            print(f"  Found {len(models)} models:")

            required_models = ["llama3.2-vision", "deepseek-r1:8b"]
            installed_models = [m.get("name", "") for m in models]

            for model in required_models:
                if any(model in installed for installed in installed_models):
                    print(f"    [OK] {model}")
                else:
                    print(f"    [FAIL] {model} not installed")
                    print(f"       Run: ollama pull {model}")

            return True

        else:
            print("  [FAIL] Ollama server returned error")
            return False

    except requests.exceptions.ConnectionError:
        print("  [FAIL] Cannot connect to Ollama server")
        print("  Please start Ollama: ollama serve")
        return False
    except Exception as e:
        print(f"  [FAIL] Ollama test failed: {e}")
        return False


def test_directories():
    """必要なディレクトリの存在チェック"""
    print("\n[*] Testing directory structure...")

    import os
    from pathlib import Path

    directories = ["uploads", "frames", "output", "logs", "static", "templates", "src"]

    all_ok = True
    for directory in directories:
        if Path(directory).exists():
            print(f"  [OK] {directory}/")
        else:
            print(f"  [WARN] {directory}/ not found (will be created)")
            try:
                Path(directory).mkdir(exist_ok=True)
                print(f"     Created {directory}/")
            except Exception as e:
                print(f"     [FAIL] Failed to create {directory}/: {e}")
                all_ok = False

    return all_ok


def test_config_file():
    """設定ファイルの存在チェック"""
    print("\n[*] Testing configuration...")

    from pathlib import Path
    import yaml

    config_file = Path("config.yaml")

    if not config_file.exists():
        print("  [FAIL] config.yaml not found")
        return False

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        print("  [OK] config.yaml loaded")

        # 重要な設定をチェック
        if "ollama" in config:
            print(f"     Ollama URL: {config['ollama']['base_url']}")

        if "web" in config:
            print(f"     Web port: {config['web']['port']}")

        return True

    except Exception as e:
        print(f"  [FAIL] Failed to load config.yaml: {e}")
        return False


def main():
    """メインテスト関数"""
    print("=" * 50)
    print("Auto-FPS-Clipper Setup Test")
    print("=" * 50)

    tests = [
        ("Python Version", test_python_version),
        ("Python Packages", test_package_imports),
        ("FFmpeg", test_ffmpeg),
        ("Ollama", test_ollama),
        ("Directories", test_directories),
        ("Configuration", test_config_file)
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n[FAIL] Test '{test_name}' crashed: {e}")
            results[test_name] = False

    # サマリー
    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)

    total = len(results)
    passed = sum(1 for result in results.values() if result)

    for test_name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} - {test_name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n[SUCCESS] All tests passed! System is ready to run.")
        print("\nTo start the application:")
        print("  Windows: start.bat")
        print("  Linux/Mac: python app.py")
    else:
        print("\n[WARNING] Some tests failed. Please fix the issues above.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
