"""
Ollama Client Module
Ollama APIとの連携（Vision & Thinking）
"""

import requests
import base64
import logging
import asyncio
from typing import List, Dict, Optional
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class OllamaClient:
    """Ollama APIクライアント"""

    def __init__(self, config: dict):
        self.config = config
        self.base_url = config["ollama"]["base_url"]
        self.vision_model = config["ollama"]["vision_model"]
        self.thinking_model = config["ollama"]["thinking_model"]
        self.timeout = config["ollama"]["timeout"]

    def _encode_image(self, image_path: str) -> str:
        """画像をBase64エンコード"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    async def analyze_frame(self, frame_path: str) -> Dict:
        """
        Llama 3.2 Visionを使用してフレームを解析

        Args:
            frame_path: フレーム画像のパス

        Returns:
            解析結果の辞書
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._analyze_frame_sync, frame_path)

    def _analyze_frame_sync(self, frame_path: str) -> Dict:
        """同期版のフレーム解析"""
        try:
            # 画像をBase64エンコード
            image_base64 = self._encode_image(frame_path)

            # プロンプト作成
            prompt = self._create_vision_prompt()

            # Ollama APIリクエスト
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.vision_model,
                    "prompt": prompt,
                    "images": [image_base64],
                    "stream": False,
                    "format": "json"
                },
                timeout=self.timeout
            )

            response.raise_for_status()
            result = response.json()

            # レスポンスをパース
            try:
                analysis = json.loads(result.get("response", "{}"))
            except json.JSONDecodeError:
                # JSONパースに失敗した場合、テキストレスポンスをそのまま使用
                analysis = {
                    "raw_response": result.get("response", ""),
                    "kill_log": False,
                    "match_status": "unknown",
                    "action_intensity": "low"
                }

            # フレームパスとタイムスタンプを追加
            frame_name = Path(frame_path).name
            timestamp = self._extract_timestamp(frame_name)

            analysis["frame_path"] = frame_path
            analysis["timestamp"] = timestamp

            logger.debug(f"Frame analysis completed: {frame_name}")

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing frame {frame_path}: {e}")
            return {
                "frame_path": frame_path,
                "timestamp": self._extract_timestamp(Path(frame_path).name),
                "error": str(e),
                "kill_log": False,
                "match_status": "unknown",
                "action_intensity": "low"
            }

    def _create_vision_prompt(self) -> str:
        """Vision解析用のプロンプトを作成"""
        return """Analyze this FPS game screenshot and provide a JSON response with the following fields:

{
    "kill_log": boolean,  // Is there a kill notification/log visible on screen?
    "match_status": string,  // "playing", "victory", "defeat", "result_screen", or "unknown"
    "action_intensity": string,  // "low", "medium", or "high" based on visual action/combat
    "enemy_visible": boolean,  // Are enemy players visible?
    "ui_elements": string,  // Brief description of visible UI elements
    "scene_description": string  // Brief description of what's happening
}

Only respond with valid JSON, no additional text."""

    async def determine_clips(self, analysis_results: List[Dict]) -> List[Dict]:
        """
        DeepSeek-R1を使用してハイライトクリップを決定

        Args:
            analysis_results: フレーム解析結果のリスト

        Returns:
            クリップ情報のリスト [{"start": 10.0, "end": 25.0, "reason": "3 kills"}, ...]
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._determine_clips_sync, analysis_results)

    def _determine_clips_sync(self, analysis_results: List[Dict]) -> List[Dict]:
        """同期版のクリップ決定"""
        try:
            # 解析結果をプロンプトに変換
            prompt = self._create_thinking_prompt(analysis_results)

            # Ollama APIリクエスト
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.thinking_model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                },
                timeout=self.timeout * 2  # Thinkingモデルは時間がかかる
            )

            response.raise_for_status()
            result = response.json()

            # レスポンスをパース
            try:
                clips_data = json.loads(result.get("response", "{}"))
                clips = clips_data.get("clips", [])
            except json.JSONDecodeError:
                logger.error("Failed to parse thinking model response")
                clips = self._fallback_clip_detection(analysis_results)

            logger.info(f"Determined {len(clips)} highlight clips")

            return clips

        except Exception as e:
            logger.error(f"Error determining clips: {e}")
            return self._fallback_clip_detection(analysis_results)

    def _create_thinking_prompt(self, analysis_results: List[Dict]) -> str:
        """Thinking用のプロンプトを作成"""
        # 解析結果をテキストに変換
        timeline = []
        for result in analysis_results:
            timestamp = result.get("timestamp", 0)
            kill_log = result.get("kill_log", False)
            action = result.get("action_intensity", "low")

            timeline.append(f"[{timestamp:.1f}s] Kill: {kill_log}, Action: {action}")

        timeline_text = "\n".join(timeline)

        return f"""You are a video editing assistant. Based on the following FPS game frame analysis timeline, identify the best highlight clips.

Timeline:
{timeline_text}

Criteria for highlight clips:
1. Scenes with kill_log = true (kills happened)
2. Scenes with action_intensity = "high"
3. Include 5-10 seconds before and after the action for context
4. Minimum clip length: 10 seconds
5. Maximum clip length: 30 seconds
6. Avoid overlapping clips

Respond with JSON in this format:
{{
    "clips": [
        {{"start": 10.0, "end": 25.0, "reason": "3 consecutive kills"}},
        {{"start": 45.0, "end": 60.0, "reason": "intense firefight"}}
    ]
}}

Only respond with valid JSON, no additional text."""

    def _fallback_clip_detection(self, analysis_results: List[Dict]) -> List[Dict]:
        """フォールバック: シンプルなルールベースのクリップ検出"""
        clips = []
        kill_timestamps = []

        # キルログがあるタイムスタンプを収集
        for result in analysis_results:
            if result.get("kill_log", False):
                kill_timestamps.append(result.get("timestamp", 0))

        # 連続するキルをグループ化
        if kill_timestamps:
            current_clip_start = kill_timestamps[0] - 5  # 5秒前から
            last_timestamp = kill_timestamps[0]

            for timestamp in kill_timestamps[1:]:
                if timestamp - last_timestamp > 10:  # 10秒以上離れている
                    # 現在のクリップを保存
                    clips.append({
                        "start": max(0, current_clip_start),
                        "end": last_timestamp + 5,  # 5秒後まで
                        "reason": "Kill sequence"
                    })
                    # 新しいクリップを開始
                    current_clip_start = timestamp - 5
                last_timestamp = timestamp

            # 最後のクリップを保存
            clips.append({
                "start": max(0, current_clip_start),
                "end": last_timestamp + 5,
                "reason": "Kill sequence"
            })

        logger.info(f"Fallback detection found {len(clips)} clips")
        return clips

    def _extract_timestamp(self, frame_name: str) -> float:
        """フレームファイル名からタイムスタンプを抽出"""
        try:
            # ファイル名形式: frame_000001_t12.34s.jpg
            parts = frame_name.split("_t")
            if len(parts) > 1:
                time_str = parts[1].replace("s.jpg", "").replace("s.png", "")
                return float(time_str)
        except Exception as e:
            logger.warning(f"Could not extract timestamp from {frame_name}: {e}")

        return 0.0

    def test_connection(self) -> bool:
        """Ollama接続テスト"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            logger.info("Ollama connection successful")
            return True
        except Exception as e:
            logger.error(f"Ollama connection failed: {e}")
            return False
