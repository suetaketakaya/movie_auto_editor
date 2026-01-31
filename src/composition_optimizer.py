"""
Composition Optimizer Module
動画の構成を最適化して視聴維持率を向上
"""

import logging
from typing import List, Dict, Optional
import statistics

logger = logging.getLogger(__name__)


class CompositionOptimizer:
    """動画構成最適化クラス"""

    def __init__(self, config: dict):
        self.config = config
        self.comp_config = config.get("composition", {})
        self.target_duration = self.comp_config.get("target_duration", 180)  # 3分
        self.min_clip_length = self.comp_config.get("min_clip_length", 3.0)
        self.max_clip_length = self.comp_config.get("max_clip_length", 15.0)
        self.optimal_pace = self.comp_config.get("optimal_pace", 5.0)  # 平均クリップ長

    def optimize_clips(self, clips: List[Dict], analysis_results: List[Dict]) -> List[Dict]:
        """
        クリップを最適化

        Args:
            clips: クリップリスト [{start, end}, ...]
            analysis_results: AI分析結果

        Returns:
            最適化されたクリップリスト
        """
        logger.info(f"Optimizing {len(clips)} clips")

        # 1. クリップにスコアを付与
        scored_clips = self._score_clips(clips, analysis_results)

        # 2. 長さを調整
        adjusted_clips = self._adjust_clip_lengths(scored_clips)

        # 3. スコア順に並び替え（ベストクリップを先に）
        sorted_clips = self._sort_clips_by_score(adjusted_clips)

        # 4. 目標時間に合わせてクリップ数を調整
        optimized_clips = self._trim_to_target_duration(sorted_clips)

        # 5. ペース調整（飽きさせないリズム作り）
        final_clips = self._optimize_pacing(optimized_clips)

        logger.info(f"Optimized to {len(final_clips)} clips, total duration: {self._total_duration(final_clips):.1f}s")

        return final_clips

    def _score_clips(self, clips: List[Dict], analysis_results: List[Dict]) -> List[Dict]:
        """クリップにスコアを付与"""
        scored = []

        for clip in clips:
            # クリップの中間時点
            mid_time = (clip["start"] + clip["end"]) / 2

            # 最も近い分析結果を取得
            closest_analysis = min(
                analysis_results,
                key=lambda x: abs(x.get("timestamp", 0) - mid_time)
            )

            # スコア計算
            score = 0

            # キルログがあれば高スコア
            if closest_analysis.get("kill_log", False):
                score += 10

            # アクション強度に応じたスコア
            action_intensity = closest_analysis.get("action_intensity", "low")
            intensity_scores = {"very_high": 8, "high": 6, "medium": 4, "low": 2}
            score += intensity_scores.get(action_intensity, 0)

            # マッチステータス
            match_status = closest_analysis.get("match_status", "normal")
            if match_status == "victory":
                score += 5
            elif match_status == "clutch":
                score += 7

            # クリップの長さもスコアに影響（長すぎると減点）
            duration = clip["end"] - clip["start"]
            if duration > self.max_clip_length:
                score -= 2
            elif duration < self.min_clip_length:
                score -= 1

            scored.append({
                **clip,
                "score": score,
                "action_intensity": action_intensity
            })

        return scored

    def _adjust_clip_lengths(self, clips: List[Dict]) -> List[Dict]:
        """クリップの長さを調整"""
        adjusted = []

        for clip in clips:
            duration = clip["end"] - clip["start"]

            # 長すぎるクリップを分割
            if duration > self.max_clip_length:
                # ハイライト部分を中心に切り出し
                center = (clip["start"] + clip["end"]) / 2
                half_max = self.max_clip_length / 2
                new_start = max(clip["start"], center - half_max)
                new_end = min(clip["end"], center + half_max)

                adjusted.append({
                    **clip,
                    "start": new_start,
                    "end": new_end
                })
            # 短すぎるクリップは前後を延長
            elif duration < self.min_clip_length:
                extension = (self.min_clip_length - duration) / 2
                adjusted.append({
                    **clip,
                    "start": clip["start"] - extension,
                    "end": clip["end"] + extension
                })
            else:
                adjusted.append(clip)

        return adjusted

    def _sort_clips_by_score(self, clips: List[Dict]) -> List[Dict]:
        """スコア順にソート（高い順）"""
        return sorted(clips, key=lambda x: x.get("score", 0), reverse=True)

    def _trim_to_target_duration(self, clips: List[Dict]) -> List[Dict]:
        """目標時間に合わせてクリップ数を調整"""
        if not clips:
            return clips

        current_duration = self._total_duration(clips)

        # 目標時間を超えている場合、低スコアのクリップを削除
        if current_duration > self.target_duration:
            trimmed = []
            accumulated_duration = 0

            for clip in clips:
                clip_duration = clip["end"] - clip["start"]

                if accumulated_duration + clip_duration <= self.target_duration:
                    trimmed.append(clip)
                    accumulated_duration += clip_duration
                else:
                    # 残り時間に収まるようクリップを短縮
                    remaining = self.target_duration - accumulated_duration
                    if remaining >= self.min_clip_length:
                        trimmed.append({
                            **clip,
                            "end": clip["start"] + remaining
                        })
                    break

            return trimmed

        return clips

    def _optimize_pacing(self, clips: List[Dict]) -> List[Dict]:
        """
        ペース最適化
        - 高強度クリップと中強度クリップを交互に配置
        - 視聴者を飽きさせないリズムを作る
        """
        if len(clips) <= 2:
            return clips

        # 強度別に分類
        high_intensity = [c for c in clips if c.get("action_intensity") in ["very_high", "high"]]
        medium_intensity = [c for c in clips if c.get("action_intensity") == "medium"]
        low_intensity = [c for c in clips if c.get("action_intensity") == "low"]

        # 交互配置
        optimized = []
        hi_idx = 0
        mi_idx = 0

        # 最初は必ず高強度で始める（フック）
        if high_intensity:
            optimized.append(high_intensity[hi_idx])
            hi_idx += 1

        # 高強度と中強度を交互に
        while hi_idx < len(high_intensity) or mi_idx < len(medium_intensity):
            if mi_idx < len(medium_intensity):
                optimized.append(medium_intensity[mi_idx])
                mi_idx += 1

            if hi_idx < len(high_intensity):
                optimized.append(high_intensity[hi_idx])
                hi_idx += 1

        # 低強度は最後に（あまり使わない）
        optimized.extend(low_intensity[:2])  # 最大2個まで

        return optimized

    def _total_duration(self, clips: List[Dict]) -> float:
        """クリップの合計時間を計算"""
        return sum(clip["end"] - clip["start"] for clip in clips)

    def create_hook_intro(self, clips: List[Dict]) -> Dict:
        """
        最初の3秒用のフッククリップを作成
        （最もスコアの高い1-3秒を最初に見せる）

        Returns:
            フック用クリップ情報
        """
        if not clips:
            return None

        # 最高スコアのクリップ
        best_clip = max(clips, key=lambda x: x.get("score", 0))

        # 最も盛り上がる3秒を抽出
        mid_point = (best_clip["start"] + best_clip["end"]) / 2

        return {
            "start": mid_point - 1.5,
            "end": mid_point + 1.5,
            "is_hook": True
        }

    def suggest_chapters(self, clips: List[Dict]) -> List[Dict]:
        """
        チャプターポイントを提案（YouTube用）

        Returns:
            チャプター情報 [{timestamp, title}, ...]
        """
        if len(clips) < 3:
            return []

        chapters = [{"timestamp": 0.0, "title": "Intro"}]

        # 5クリップごとにチャプター
        accumulated_time = 0
        for i, clip in enumerate(clips):
            if i > 0 and i % 5 == 0:
                chapters.append({
                    "timestamp": accumulated_time,
                    "title": f"Highlight {i // 5}"
                })

            accumulated_time += clip["end"] - clip["start"]

        return chapters

    def analyze_engagement_curve(self, clips: List[Dict]) -> Dict:
        """
        エンゲージメント曲線を分析

        Returns:
            分析結果
        """
        if not clips:
            return {"status": "no_clips"}

        scores = [c.get("score", 0) for c in clips]

        return {
            "avg_score": statistics.mean(scores) if scores else 0,
            "score_variance": statistics.variance(scores) if len(scores) > 1 else 0,
            "peak_moment": max(range(len(scores)), key=lambda i: scores[i]) if scores else 0,
            "total_duration": self._total_duration(clips),
            "clip_count": len(clips),
            "pacing_score": self._calculate_pacing_score(clips)
        }

    def _calculate_pacing_score(self, clips: List[Dict]) -> float:
        """
        ペーススコアを計算
        理想的なペースに近いほど高スコア
        """
        if not clips:
            return 0.0

        durations = [c["end"] - c["start"] for c in clips]
        avg_duration = statistics.mean(durations)

        # 理想的なペース（5秒）との差を評価
        deviation = abs(avg_duration - self.optimal_pace)

        # 0-100のスコア
        return max(0, 100 - (deviation * 10))
