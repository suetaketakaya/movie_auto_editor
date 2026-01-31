"""
Engagement Prediction Module
エンゲージメント予測AI - 視聴維持率予測
"""

import logging
from typing import List, Dict
import statistics

logger = logging.getLogger(__name__)


class EngagementPredictor:
    """エンゲージメント予測クラス"""

    def __init__(self, config: dict):
        self.config = config

    def predict_engagement_score(self, clips: List[Dict], analysis_results: List[Dict]) -> Dict:
        """
        動画のエンゲージメントスコアを予測

        Args:
            clips: クリップリスト
            analysis_results: AI分析結果

        Returns:
            予測結果
        """
        logger.info("Predicting engagement score")

        # 簡易予測モデル
        scores = {
            "overall_score": 0,
            "retention_prediction": 0,
            "click_through_rate": 0,
            "watch_time_minutes": 0
        }

        if not clips:
            return scores

        # 1. 平均興奮度
        excitement_scores = [r.get("excitement_score", 0) for r in analysis_results]
        avg_excitement = statistics.mean(excitement_scores) if excitement_scores else 0

        # 2. クリップのバラエティ
        clip_lengths = [c["end"] - c["start"] for c in clips]
        variety_score = statistics.stdev(clip_lengths) if len(clip_lengths) > 1 else 0

        # 3. 総動画長
        total_duration = sum(clip_lengths)

        # スコア計算
        scores["overall_score"] = min(100, int(avg_excitement * 2 + variety_score * 5))
        scores["retention_prediction"] = min(100, int((avg_excitement / 30) * 100))
        scores["click_through_rate"] = min(15, int(avg_excitement / 5))
        scores["watch_time_minutes"] = total_duration / 60

        logger.info(f"Predicted engagement score: {scores['overall_score']}")
        return scores

    def detect_drop_off_points(self, clips: List[Dict]) -> List[float]:
        """離脱ポイントを検出"""
        drop_offs = []

        for i, clip in enumerate(clips):
            duration = clip["end"] - clip["start"]
            # 長すぎるクリップは離脱リスク
            if duration > 15:
                drop_offs.append(clip["start"])

        return drop_offs

    def suggest_improvements(self, clips: List[Dict], analysis_results: List[Dict]) -> List[str]:
        """改善提案"""
        suggestions = []

        total_duration = sum([c["end"] - c["start"] for c in clips])

        if total_duration > 300:
            suggestions.append("動画が長すぎます。3-5分に短縮することを推奨します")

        if len(clips) > 15:
            suggestions.append("クリップ数が多すぎます。ベストシーンのみに絞ることを推奨します")

        return suggestions
