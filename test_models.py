"""
モデル性能テストスクリプト
各ビジョンモデルの精度を比較
"""

import asyncio
import yaml
from pathlib import Path
from src.multi_model_analyzer import MultiModelAnalyzer
from src.ollama_client import OllamaClient


async def test_models():
    """モデルのテスト"""
    # 設定読み込み
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # テスト画像パス (D:/公開動画/素材 から適当な画像を使用)
    test_image = "D:/公開動画/素材/test_frame.jpg"  # ユーザーが用意

    if not Path(test_image).exists():
        print(f"❌ テスト画像が見つかりません: {test_image}")
        print("D:/公開動画/素材 に test_frame.jpg を配置してください")
        return

    print("=" * 60)
    print("🧪 ビジョンモデル性能テスト")
    print("=" * 60)
    print()

    # 各モデルをテスト
    models_to_test = [
        ("qwen2-vl:7b", "Qwen2-VL 7B"),
        ("llama3.2-vision", "Llama 3.2 Vision"),
        ("llava:13b", "LLaVA 13B")
    ]

    results = []

    for model_name, display_name in models_to_test:
        print(f"📊 {display_name} をテスト中...")

        # モデル設定
        test_config = config.copy()
        test_config["ollama"]["vision_model"] = model_name

        try:
            client = OllamaClient(test_config)
            result = await client.analyze_frame(test_image)

            print(f"✅ {display_name}")
            print(f"   - キルログ検出: {result.get('kill_log', False)}")
            print(f"   - アクション強度: {result.get('action_intensity', 'N/A')}")
            print(f"   - 信頼度: {result.get('confidence', 0):.2f}")
            print()

            results.append({
                "model": display_name,
                "result": result
            })

        except Exception as e:
            print(f"❌ {display_name} エラー: {e}")
            print()

    # マルチモデル分析テスト
    print("=" * 60)
    print("🔬 マルチモデル分析テスト (アンサンブル)")
    print("=" * 60)
    print()

    multi_config = config.copy()
    multi_config["multi_model"]["enable"] = True
    multi_config["multi_model"]["strategy"] = "ensemble"

    try:
        multi_analyzer = MultiModelAnalyzer(multi_config)
        ensemble_result = await multi_analyzer.analyze_frame(test_image)

        print("✅ アンサンブル結果:")
        print(f"   - キルログ検出: {ensemble_result.get('kill_log', False)}")
        print(f"   - アクション強度: {ensemble_result.get('action_intensity', 'N/A')}")
        print(f"   - 平均信頼度: {ensemble_result.get('confidence', 0):.2f}")
        print(f"   - 使用モデル数: {ensemble_result.get('ensemble_votes', 0)}")
        print()

    except Exception as e:
        print(f"❌ アンサンブル分析エラー: {e}")
        print()

    print("=" * 60)
    print("✅ テスト完了")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_models())
