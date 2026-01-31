"""
Multi-Model Vision Analysis
複数モデル併用による高精度AI分析
"""

import logging
import asyncio
from typing import List, Dict, Optional
from collections import Counter
from src.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class MultiModelAnalyzer:
    """複数ビジョンモデルを使った高精度分析"""

    def __init__(self, config: dict):
        self.config = config
        self.multi_config = config.get("multi_model", {})
        self.enabled = self.multi_config.get("enable", False)

        # 使用するモデルリスト
        self.models = self.multi_config.get("models", [
            "qwen2-vl:7b",
            "llama3.2-vision",
            "llava:13b"
        ])

        # 各モデル用のクライアント
        self.clients = {}
        for model in self.models:
            model_config = config.copy()
            model_config["ollama"]["vision_model"] = model
            self.clients[model] = OllamaClient(model_config)

        self.strategy = self.multi_config.get("strategy", "ensemble")  # ensemble, confidence, specialized
        logger.info(f"MultiModelAnalyzer initialized with {len(self.models)} models: {self.models}")
        logger.info(f"Strategy: {self.strategy}")

    async def analyze_frame(self, frame_path: str) -> Dict:
        """
        複数モデルでフレームを分析

        Args:
            frame_path: フレーム画像パス

        Returns:
            統合された分析結果
        """
        if not self.enabled or len(self.models) == 1:
            # シングルモデルモード
            return await self.clients[self.models[0]].analyze_frame(frame_path)

        if self.strategy == "ensemble":
            return await self._ensemble_analysis(frame_path)
        elif self.strategy == "confidence":
            return await self._confidence_based_analysis(frame_path)
        elif self.strategy == "specialized":
            return await self._specialized_analysis(frame_path)
        else:
            return await self._ensemble_analysis(frame_path)

    async def _ensemble_analysis(self, frame_path: str) -> Dict:
        """
        アンサンブル投票方式
        全モデルで解析 → 多数決
        """
        logger.info(f"Ensemble analysis with {len(self.models)} models")

        # 全モデルで並列解析
        tasks = [
            client.analyze_frame(frame_path)
            for client in self.clients.values()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # エラーハンドリング
        valid_results = [r for r in results if not isinstance(r, Exception)]
        if not valid_results:
            logger.error("All models failed!")
            return self._default_result(frame_path)

        # 投票
        kill_log_votes = [r.get("kill_log", False) for r in valid_results]
        kill_log = Counter(kill_log_votes).most_common(1)[0][0]

        action_intensities = [r.get("action_intensity", "low") for r in valid_results]
        action_intensity = Counter(action_intensities).most_common(1)[0][0]

        match_statuses = [r.get("match_status", "normal") for r in valid_results]
        match_status = Counter(match_statuses).most_common(1)[0][0]

        # 平均信頼度
        confidences = [r.get("confidence", 0.5) for r in valid_results]
        avg_confidence = sum(confidences) / len(confidences)

        # 統合結果
        ensemble_result = {
            "timestamp": valid_results[0].get("timestamp", 0),
            "kill_log": kill_log,
            "action_intensity": action_intensity,
            "match_status": match_status,
            "confidence": avg_confidence,
            "ensemble_votes": len(valid_results),
            "models_used": [m for m, r in zip(self.models, results) if not isinstance(r, Exception)]
        }

        logger.info(f"Ensemble result: kill_log={kill_log} (confidence={avg_confidence:.2f})")
        return ensemble_result

    async def _confidence_based_analysis(self, frame_path: str) -> Dict:
        """
        信頼度ベース方式
        プライマリモデルで解析 → 信頼度低い場合のみセカンダリで再解析
        """
        primary_model = self.models[0]
        secondary_models = self.models[1:]

        logger.info(f"Confidence-based analysis: primary={primary_model}")

        # プライマリモデルで解析
        primary_client = self.clients[primary_model]
        result = await primary_client.analyze_frame(frame_path)

        confidence = result.get("confidence", 0.5)
        threshold = self.multi_config.get("confidence_threshold", 0.7)

        # 信頼度が低い場合のみ追加解析
        if confidence < threshold and secondary_models:
            logger.info(f"Low confidence ({confidence:.2f}), running secondary analysis")

            # セカンダリモデルで再解析
            secondary_client = self.clients[secondary_models[0]]
            secondary_result = await secondary_client.analyze_frame(frame_path)

            # より信頼度の高い結果を採用
            if secondary_result.get("confidence", 0) > confidence:
                logger.info("Using secondary model result (higher confidence)")
                result = secondary_result
                result["fallback_used"] = True
            else:
                result["fallback_checked"] = True

        return result

    async def _specialized_analysis(self, frame_path: str) -> Dict:
        """
        専門化分担方式
        各モデルが得意分野を担当
        """
        logger.info("Specialized analysis with task division")

        # 役割分担
        # Model 1 (Qwen2-VL): キルログ検出
        # Model 2 (LLaVA): UI要素・アクション強度
        # Model 3 (Moondream): シーン分類

        tasks = []
        for model, client in zip(self.models, self.clients.values()):
            tasks.append(client.analyze_frame(frame_path))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 有効な結果のみ
        valid_results = [r for r in results if not isinstance(r, Exception)]
        if not valid_results:
            return self._default_result(frame_path)

        # 各モデルの得意分野を統合
        combined_result = {
            "timestamp": valid_results[0].get("timestamp", 0),
            "kill_log": results[0].get("kill_log", False) if len(results) > 0 else False,  # Qwen2-VL
            "action_intensity": results[1].get("action_intensity", "low") if len(results) > 1 else "low",  # LLaVA
            "match_status": valid_results[0].get("match_status", "normal"),
            "confidence": sum([r.get("confidence", 0.5) for r in valid_results]) / len(valid_results),
            "specialized": True
        }

        return combined_result

    def _default_result(self, frame_path: str) -> Dict:
        """デフォルトの解析結果"""
        from pathlib import Path
        timestamp = float(Path(frame_path).stem.split("_")[-1]) / 1000
        return {
            "timestamp": timestamp,
            "kill_log": False,
            "action_intensity": "low",
            "match_status": "normal",
            "confidence": 0.0
        }

    def get_model_stats(self) -> Dict:
        """モデル統計情報を取得"""
        return {
            "enabled": self.enabled,
            "strategy": self.strategy,
            "models": self.models,
            "model_count": len(self.models)
        }
