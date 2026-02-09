"""
Advanced AI Analyzer Module
高度なAI分析機能
"""

import logging
from typing import List, Dict, Optional
import statistics

logger = logging.getLogger(__name__)


class AdvancedAnalyzer:
    """高度なAI分析クラス"""

    def __init__(self, config: dict):
        self.config = config
        self.analysis_config = config.get("advanced_analysis", {})

    def analyze_excitement_level(self, analysis_results: List[Dict]) -> List[Dict]:
        """
        興奮度を分析してスコア化

        Args:
            analysis_results: AI分析結果のリスト

        Returns:
            興奮度スコア付き分析結果
        """
        logger.info("Analyzing excitement levels")

        enhanced_results = []

        for result in analysis_results:
            excitement_score = 0

            # キルログ
            if result.get("kill_log", False):
                excitement_score += 20

            # アクション強度
            action_intensity = result.get("action_intensity", "low")
            intensity_scores = {
                "very_high": 15,
                "high": 10,
                "medium": 5,
                "low": 0
            }
            excitement_score += intensity_scores.get(action_intensity, 0)

            # マッチステータス
            match_status = result.get("match_status", "normal")
            status_scores = {
                "victory": 10,
                "clutch": 15,
                "defeat": -5,
                "normal": 0
            }
            excitement_score += status_scores.get(match_status, 0)

            enhanced_results.append({
                **result,
                "excitement_score": excitement_score
            })

        return enhanced_results

    def detect_multi_kills(self, analysis_results: List[Dict],
                          time_window: float = 10.0) -> List[Dict]:
        """
        マルチキルを検出

        Args:
            analysis_results: AI分析結果
            time_window: マルチキル判定の時間窓（秒）

        Returns:
            マルチキル情報 [{type, timestamp, kill_count}, ...]
        """
        logger.info("Detecting multi-kills")

        kill_timestamps = [
            r["timestamp"] for r in analysis_results
            if r.get("kill_log", False)
        ]

        if not kill_timestamps:
            return []

        multi_kills = []
        kill_timestamps.sort()

        i = 0
        while i < len(kill_timestamps):
            window_start = kill_timestamps[i]
            kills_in_window = 1

            # 時間窓内のキルをカウント
            j = i + 1
            while j < len(kill_timestamps) and kill_timestamps[j] - window_start <= time_window:
                kills_in_window += 1
                j += 1

            # マルチキル判定
            if kills_in_window >= 2:
                kill_type = self._classify_multi_kill(kills_in_window)
                multi_kills.append({
                    "type": kill_type,
                    "timestamp": window_start,
                    "kill_count": kills_in_window,
                    "end_timestamp": kill_timestamps[j - 1] if j > i else window_start
                })

            i = j if j > i else i + 1

        logger.info(f"Detected {len(multi_kills)} multi-kill events")
        return multi_kills

    def _classify_multi_kill(self, kill_count: int) -> str:
        """マルチキルの種類を分類"""
        if kill_count >= 5:
            return "ACE"
        elif kill_count == 4:
            return "QUAD KILL"
        elif kill_count == 3:
            return "TRIPLE KILL"
        elif kill_count == 2:
            return "DOUBLE KILL"
        return "KILL"

    def detect_clutch_moments(self, analysis_results: List[Dict]) -> List[Dict]:
        """
        クラッチモーメントを検出

        Args:
            analysis_results: AI分析結果

        Returns:
            クラッチ情報
        """
        logger.info("Detecting clutch moments")

        clutch_moments = []

        for result in analysis_results:
            if result.get("match_status") == "clutch":
                clutch_moments.append({
                    "timestamp": result["timestamp"],
                    "type": "clutch",
                    "action_intensity": result.get("action_intensity", "medium")
                })

        logger.info(f"Detected {len(clutch_moments)} clutch moments")
        return clutch_moments

    def analyze_momentum_shifts(self, analysis_results: List[Dict]) -> List[Dict]:
        """
        モメンタムシフト（流れの変化）を検出

        Args:
            analysis_results: AI分析結果

        Returns:
            モメンタムシフト情報
        """
        logger.info("Analyzing momentum shifts")

        if len(analysis_results) < 5:
            return []

        # 興奮度の時系列データ
        excitement_timeline = [
            (r["timestamp"], r.get("excitement_score", 0))
            for r in analysis_results
            if "excitement_score" in r
        ]

        if not excitement_timeline:
            return []

        shifts = []

        # 移動平均でトレンドを計算
        window_size = 5
        for i in range(len(excitement_timeline) - window_size):
            window_before = excitement_timeline[i:i + window_size]
            window_after = excitement_timeline[i + window_size:i + window_size * 2]

            if len(window_after) < window_size:
                break

            avg_before = statistics.mean([x[1] for x in window_before])
            avg_after = statistics.mean([x[1] for x in window_after])

            # 大きな変化を検出
            change = avg_after - avg_before

            if abs(change) > 10:  # 閾値
                shifts.append({
                    "timestamp": excitement_timeline[i + window_size][0],
                    "type": "momentum_up" if change > 0 else "momentum_down",
                    "magnitude": abs(change)
                })

        logger.info(f"Detected {len(shifts)} momentum shifts")
        return shifts

    def suggest_highlights_from_patterns(self, analysis_results: List[Dict],
                                        multi_kills: List[Dict],
                                        clutch_moments: List[Dict]) -> List[Dict]:
        """
        パターン分析からハイライトを提案

        Args:
            analysis_results: AI分析結果
            multi_kills: マルチキル情報
            clutch_moments: クラッチ情報

        Returns:
            推奨ハイライトクリップ
        """
        logger.info("Suggesting highlights from patterns")

        highlights = []

        # マルチキルは必ず含める
        for mk in multi_kills:
            highlights.append({
                "start": max(0, mk["timestamp"] - 3),
                "end": mk.get("end_timestamp", mk["timestamp"]) + 3,
                "type": "multi_kill",
                "priority": 10,
                "label": mk["type"]
            })

        # クラッチモーメント
        for cm in clutch_moments:
            highlights.append({
                "start": max(0, cm["timestamp"] - 5),
                "end": cm["timestamp"] + 5,
                "type": "clutch",
                "priority": 9,
                "label": "CLUTCH"
            })

        # 高興奮度シーン
        for result in analysis_results:
            if result.get("excitement_score", 0) >= 25:
                highlights.append({
                    "start": max(0, result["timestamp"] - 2),
                    "end": result["timestamp"] + 3,
                    "type": "high_excitement",
                    "priority": 7,
                    "label": "INTENSE"
                })

        # 優先度順にソート
        highlights.sort(key=lambda x: x.get("priority", 0), reverse=True)

        # 重複を削除（時間が重なるクリップをマージ）
        merged_highlights = self._merge_overlapping_clips(highlights)

        logger.info(f"Suggested {len(merged_highlights)} highlight clips")
        return merged_highlights

    def _merge_overlapping_clips(self, clips: List[Dict]) -> List[Dict]:
        """重複するクリップをマージ"""
        if not clips:
            return []

        # 開始時間でソート
        sorted_clips = sorted(clips, key=lambda x: x["start"])

        merged = [sorted_clips[0]]

        for current in sorted_clips[1:]:
            last = merged[-1]

            # 重複チェック
            if current["start"] <= last["end"]:
                # マージ
                merged[-1] = {
                    "start": min(last["start"], current["start"]),
                    "end": max(last["end"], current["end"]),
                    "type": last["type"],  # 優先度の高い方のタイプを維持
                    "priority": max(last.get("priority", 0), current.get("priority", 0)),
                    "label": last.get("label", "")
                }
            else:
                merged.append(current)

        return merged

    def calculate_clip_quality_score(self, clip: Dict, analysis_results: List[Dict]) -> float:
        """
        クリップの品質スコアを計算

        Args:
            clip: クリップ情報
            analysis_results: AI分析結果

        Returns:
            品質スコア（0-100）
        """
        # クリップ内の分析結果を取得
        clip_analyses = [
            r for r in analysis_results
            if clip["start"] <= r.get("timestamp", 0) <= clip["end"]
        ]

        if not clip_analyses:
            return 0.0

        score = 0.0

        # 平均興奮度
        avg_excitement = statistics.mean([
            r.get("excitement_score", 0) for r in clip_analyses
        ])
        score += min(50, avg_excitement * 2)

        # クリップの長さ（5-10秒が理想）
        duration = clip["end"] - clip["start"]
        if 5 <= duration <= 10:
            score += 20
        elif 3 <= duration <= 15:
            score += 10

        # アクション密度（キル数/秒）
        kill_count = sum(1 for r in clip_analyses if r.get("kill_log", False))
        action_density = kill_count / duration if duration > 0 else 0
        score += min(30, action_density * 100)

        return min(100.0, score)

    def analyze_video_variety(self, clips: List[Dict]) -> Dict:
        """
        動画のバラエティを分析

        Args:
            clips: クリップリスト

        Returns:
            バラエティ分析結果
        """
        if not clips:
            return {"variety_score": 0, "issues": ["no_clips"]}

        # クリップタイプの分布
        types = [c.get("type", "unknown") for c in clips]
        unique_types = len(set(types))

        # クリップ長のバラエティ
        durations = [c["end"] - c["start"] for c in clips]
        duration_variance = statistics.variance(durations) if len(durations) > 1 else 0

        # バラエティスコア計算
        variety_score = (unique_types * 20) + min(30, duration_variance * 5)

        issues = []
        if unique_types < 2:
            issues.append("low_type_variety")
        if duration_variance < 2:
            issues.append("uniform_clip_lengths")

        return {
            "variety_score": min(100, variety_score),
            "unique_types": unique_types,
            "duration_variance": duration_variance,
            "issues": issues
        }
