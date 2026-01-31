# Auto-FPS-Clipper クイックスタートガイド

## システム完成しました！ 🎉

FFmpeg、Ollama、必要なPythonパッケージがすべてインストールされました。

## ⚠️ 重要: FFmpegのPATH設定

FFmpegをインストールしましたが、**ターミナルを再起動**する必要があります。

```bash
# 現在のターミナルを閉じて、新しいターミナルを開く
# そして動作確認:
ffmpeg -version
```

## 🚀 起動方法

### 方法1: start.batを使用（推奨）

```bash
# プロジェクトディレクトリで
start.bat
```

### 方法2: 手動起動

```bash
# 1. 仮想環境をアクティベート
venv\Scripts\activate

# 2. アプリケーションを起動
python app.py
```

## 🌐 アクセス

ブラウザで以下のURLを開く:
```
http://localhost:8000
```

## 📝 使い方

1. **動画をアップロード**
   - ブラウザでドラッグ&ドロップ
   - 対応形式: MP4, MKV, AVI, MOV

2. **自動処理**
   - フレーム抽出（2秒間隔）
   - AI解析（Ollama Llama 3.2 Vision）
   - ハイライト検出
   - 動画生成（FFmpeg）

3. **ダウンロード**
   - 処理完了後、ダウンロードボタンから取得

## 🔧 設定カスタマイズ

`config.yaml`を編集して以下を調整可能:

```yaml
# フレーム抽出間隔（秒）
frame_extraction:
  interval_seconds: 2  # 2秒おきにフレームを抽出

# 動画品質
export:
  crf: 18  # 低いほど高画質（18推奨）
  preset: "slow"  # slow = 高品質、fast = 高速

# 使用モデル
ollama:
  vision_model: "llama3.2-vision"
  thinking_model: "llama3.2-vision"
```

## ✅ 動作確認

```bash
# セットアップテストを実行
python test_setup.py
```

すべてのテストがパスすればOKです！

## 🎮 サポートされるゲーム

- Apex Legends
- VALORANT
- Counter-Strike 2
- Call of Duty シリーズ
- Overwatch 2
- Rainbow Six Siege
- その他すべてのFPSゲーム

## 📊 処理時間の目安

- 10分動画: 約5-10分
- 30分動画: 約15-30分
- 1時間動画: 約30-60分

※GPU使用時の目安

## 🐛 トラブルシューティング

### FFmpegが見つからない

```bash
# ターミナルを再起動してから:
ffmpeg -version
```

### Ollama接続エラー

```bash
# Ollamaが起動しているか確認:
ollama list

# 起動していない場合:
# Windowsの場合、自動的に起動しているはず
# 手動起動する場合は別ターミナルで:
ollama serve
```

### ポート8000が使用中

`config.yaml`の`web.port`を変更:
```yaml
web:
  port: 8080  # 別のポート
```

## 📦 プロジェクト構造

```
movie_cutter/
├── app.py              # メインアプリケーション
├── config.yaml         # 設定ファイル
├── start.bat           # 起動スクリプト
├── src/                # バックエンドモジュール
├── static/             # フロントエンド
├── templates/          # HTMLテンプレート
└── uploads/            # アップロード先
```

## 🔄 次回以降の起動

1. ターミナルを開く
2. プロジェクトディレクトリに移動:
   ```bash
   cd C:\Users\suetake\.0progs\movie_cutter
   ```
3. `start.bat`を実行、またはダブルクリック

## 💡 ヒント

- **高品質優先**: `config.yaml`の`crf`を16に設定
- **高速処理優先**: `preset`を"fast"に設定
- **メモリ節約**: `max_frames`を200に設定

---

**Happy Clipping! 🎬✨**

詳細は`README.md`を参照してください。
