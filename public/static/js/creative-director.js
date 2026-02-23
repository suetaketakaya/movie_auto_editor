// ClipMontage — Creative Director (JS port)
// Integrates: HighlightDetector, CompositionPlanner, ClipScorer, CreativeDirector

// ═══════════════════════════════════════════════════════
// HIGHLIGHT DETECTOR
// ═══════════════════════════════════════════════════════

class HighlightDetector {
    analyzeExcitementLevels(analyses) {
        return analyses.map((a) => {
            let excitement = 0;

            if (a.killLog) {
                excitement += 25;
                if (a.killCount >= 3) excitement += 15;
                else if (a.killCount >= 2) excitement += 8;
            }

            const intensityMap = { very_high: 25, high: 18, medium: 10, low: 0 };
            excitement += intensityMap[a.actionIntensity] || 0;

            const statusMap = { victory: 10, clutch: 20, overtime: 12, defeat: -5, normal: 0 };
            excitement += statusMap[a.matchStatus] || 0;

            if (a.enemyVisible) {
                excitement += 10;
                if (a.enemyCount >= 3) excitement += 5;
            }

            if (a.confidence > 0) {
                excitement *= (0.5 + 0.5 * a.confidence);
            }

            return new FrameAnalysis({
                ...a,
                framePath: a.framePath,
                timestamp: a.timestamp,
                killLog: a.killLog,
                matchStatus: a.matchStatus,
                actionIntensity: a.actionIntensity,
                enemyVisible: a.enemyVisible,
                sceneDescription: a.sceneDescription,
                confidence: a.confidence,
                excitementScore: excitement,
                modelUsed: a.modelUsed,
                rawResponse: a.rawResponse,
                uiElements: a.uiElements,
                metadata: a.metadata,
                killCount: a.killCount,
                enemyCount: a.enemyCount,
                visualQuality: a.visualQuality,
            });
        });
    }

    detectMultiEvents(analyses, timeWindow = 10) {
        const killTimestamps = analyses
            .filter((a) => a.killLog)
            .map((a) => a.timestamp)
            .sort((a, b) => a - b);
        if (!killTimestamps.length) return [];

        const events = [];
        let i = 0;
        while (i < killTimestamps.length) {
            const windowStart = killTimestamps[i];
            let count = 1;
            let j = i + 1;
            while (j < killTimestamps.length && killTimestamps[j] - windowStart <= timeWindow) {
                count++;
                j++;
            }
            if (count >= 2) {
                events.push({
                    type: this._classifyMultiEvent(count),
                    timestamp: windowStart,
                    killCount: count,
                    endTimestamp: j > i ? killTimestamps[j - 1] : windowStart,
                });
            }
            i = j > i ? j : i + 1;
        }
        return events;
    }

    _classifyMultiEvent(count) {
        if (count >= 5) return 'ACE';
        if (count === 4) return 'QUAD KILL';
        if (count === 3) return 'TRIPLE KILL';
        if (count === 2) return 'DOUBLE KILL';
        return 'KILL';
    }

    detectClutchMoments(analyses) {
        return analyses
            .filter((a) => a.matchStatus === 'clutch')
            .map((a) => ({
                timestamp: a.timestamp,
                type: 'clutch',
                actionIntensity: a.actionIntensity,
            }));
    }

    analyzeMomentumShifts(analyses) {
        const timeline = analyses
            .filter((a) => a.excitementScore > 0)
            .map((a) => [a.timestamp, a.excitementScore]);
        if (timeline.length < 10) return [];

        const shifts = [];
        const window = 5;
        for (let i = 0; i <= timeline.length - window * 2; i++) {
            const before = timeline.slice(i, i + window).map((x) => x[1]);
            const after = timeline.slice(i + window, i + window * 2).map((x) => x[1]);
            if (after.length < window) break;
            const avgBefore = before.reduce((s, v) => s + v, 0) / before.length;
            const avgAfter = after.reduce((s, v) => s + v, 0) / after.length;
            const change = avgAfter - avgBefore;
            if (Math.abs(change) > 10) {
                shifts.push({
                    timestamp: timeline[i + window][0],
                    type: change > 0 ? 'momentum_up' : 'momentum_down',
                    magnitude: Math.abs(change),
                });
            }
        }
        return shifts;
    }

    suggestHighlights(analyses, multiEvents, clutchMoments) {
        const highlights = [];

        for (const mk of multiEvents) {
            const endTs = mk.endTimestamp || mk.timestamp;
            highlights.push(new Clip({
                timeRange: new TimeRange(Math.max(0, mk.timestamp - 3), endTs + 3),
                clipType: 'multi_kill',
                label: mk.type,
                priority: 10,
                reason: `${mk.type} (${mk.killCount} kills)`,
                score: new QualityScore(90),
            }));
        }

        for (const cm of clutchMoments) {
            highlights.push(new Clip({
                timeRange: new TimeRange(Math.max(0, cm.timestamp - 5), cm.timestamp + 5),
                clipType: 'clutch',
                label: 'CLUTCH',
                priority: 9,
                reason: 'Clutch moment',
                score: new QualityScore(80),
            }));
        }

        for (const a of analyses) {
            if (a.excitementScore >= 25) {
                highlights.push(new Clip({
                    timeRange: new TimeRange(Math.max(0, a.timestamp - 2), a.timestamp + 3),
                    clipType: 'high_excitement',
                    label: 'INTENSE',
                    priority: 7,
                    reason: 'High excitement',
                    score: new QualityScore(70),
                }));
            }
        }

        highlights.sort((a, b) => b.priority - a.priority);
        return this.mergeOverlappingClips(highlights);
    }

    mergeOverlappingClips(clips) {
        if (!clips.length) return [];
        const sorted = [...clips].sort((a, b) => a.start - b.start);
        const merged = [sorted[0]];

        for (let i = 1; i < sorted.length; i++) {
            const current = sorted[i];
            const last = merged[merged.length - 1];
            if (current.start <= last.end) {
                const newRange = new TimeRange(
                    Math.min(last.start, current.start),
                    Math.max(last.end, current.end),
                );
                const keep = last.priority >= current.priority ? last : current;
                merged[merged.length - 1] = keep.withAdjustedRange(newRange);
            } else {
                merged.push(current);
            }
        }
        return merged;
    }

    analyzeVariety(clips) {
        if (!clips.length) return { varietyScore: 0, issues: ['no_clips'] };
        const types = clips.map((c) => c.clipType || 'unknown');
        const uniqueTypes = new Set(types).size;
        const durations = clips.map((c) => c.duration);
        const durVariance = durations.length > 1 ? _variance(durations) : 0;
        const varietyScore = Math.min(100, uniqueTypes * 20 + Math.min(30, durVariance * 5));
        const issues = [];
        if (uniqueTypes < 2) issues.push('low_type_variety');
        if (durVariance < 2) issues.push('uniform_clip_lengths');
        return { varietyScore, uniqueTypes, durationVariance: durVariance, issues };
    }
}

// ═══════════════════════════════════════════════════════
// COMPOSITION PLANNER
// ═══════════════════════════════════════════════════════

class CompositionPlanner {
    constructor(opts = {}) {
        this.targetDuration = opts.targetDuration || 180;
        this.minClipLength = opts.minClipLength || 3;
        this.maxClipLength = opts.maxClipLength || 15;
        this.optimalPace = opts.optimalPace || 5;
    }

    optimizeClips(clips, analyses) {
        let result = this.scoreClips(clips, analyses);
        result = this.adjustClipLengths(result);
        result.sort((a, b) => b.score.value - a.score.value);
        result = this.trimToTargetDuration(result);
        return this.optimizePacing(result);
    }

    scoreClips(clips, analyses) {
        return clips.map((clip) => {
            const midTime = clip.timeRange.midpoint;
            let closest = null;
            let closestDist = Infinity;
            for (const a of analyses) {
                const d = Math.abs(a.timestamp - midTime);
                if (d < closestDist) { closestDist = d; closest = a; }
            }

            let score = 0;
            let actionIntensity = clip.actionIntensity;

            if (closest) {
                if (closest.killLog) score += 10;
                const intensityScores = { very_high: 8, high: 6, medium: 4, low: 2 };
                score += intensityScores[closest.actionIntensity] || 0;
                actionIntensity = closest.actionIntensity;
                if (closest.matchStatus === 'victory') score += 5;
                else if (closest.matchStatus === 'clutch') score += 7;
            }

            if (clip.duration > this.maxClipLength) score -= 2;
            else if (clip.duration < this.minClipLength) score -= 1;

            return new Clip({
                timeRange: clip.timeRange,
                reason: clip.reason,
                score: new QualityScore(Math.max(0, score)),
                clipType: clip.clipType,
                label: clip.label,
                priority: clip.priority,
                actionIntensity,
                id: clip.id,
                metadata: clip.metadata,
            });
        });
    }

    adjustClipLengths(clips) {
        return clips.map((clip) => {
            const duration = clip.duration;
            if (duration > this.maxClipLength) {
                const center = clip.timeRange.midpoint;
                const half = this.maxClipLength / 2;
                return clip.withAdjustedRange(new TimeRange(
                    Math.max(clip.start, center - half),
                    Math.min(clip.end, center + half),
                ));
            }
            if (duration < this.minClipLength) {
                const ext = (this.minClipLength - duration) / 2;
                return clip.withAdjustedRange(new TimeRange(
                    Math.max(0, clip.start - ext),
                    clip.end + ext,
                ));
            }
            return clip;
        });
    }

    trimToTargetDuration(clips) {
        if (!clips.length) return clips;
        const total = clips.reduce((s, c) => s + c.duration, 0);
        if (total <= this.targetDuration) return clips;

        const trimmed = [];
        let accumulated = 0;
        for (const clip of clips) {
            if (accumulated + clip.duration <= this.targetDuration) {
                trimmed.push(clip);
                accumulated += clip.duration;
            } else {
                const remaining = this.targetDuration - accumulated;
                if (remaining >= this.minClipLength) {
                    trimmed.push(clip.withAdjustedRange(
                        new TimeRange(clip.start, clip.start + remaining),
                    ));
                }
                break;
            }
        }
        return trimmed;
    }

    optimizePacing(clips) {
        if (clips.length <= 2) return clips;
        const high = clips.filter((c) => c.actionIntensity === 'very_high' || c.actionIntensity === 'high');
        const medium = clips.filter((c) => c.actionIntensity === 'medium');
        const low = clips.filter((c) => c.actionIntensity === 'low');

        const optimized = [];
        let hi = 0, mi = 0;
        if (high.length) { optimized.push(high[hi++]); }
        while (hi < high.length || mi < medium.length) {
            if (mi < medium.length) optimized.push(medium[mi++]);
            if (hi < high.length) optimized.push(high[hi++]);
        }
        optimized.push(...low.slice(0, 2));
        return optimized;
    }

    createHookIntro(clips) {
        if (!clips.length) return null;
        const best = clips.reduce((a, b) => a.score.value >= b.score.value ? a : b);
        const mid = best.timeRange.midpoint;
        return new Clip({
            timeRange: new TimeRange(Math.max(0, mid - 1.5), mid + 1.5),
            reason: 'hook',
            score: best.score,
            clipType: 'hook',
            label: 'HOOK',
            metadata: { isHook: true },
        });
    }

    analyzeEngagementCurve(clips) {
        if (!clips.length) return { status: 'no_clips' };
        const scores = clips.map((c) => c.score.value);
        return {
            avgScore: scores.reduce((s, v) => s + v, 0) / scores.length,
            scoreVariance: scores.length > 1 ? _variance(scores) : 0,
            peakMoment: scores.indexOf(Math.max(...scores)),
            totalDuration: clips.reduce((s, c) => s + c.duration, 0),
            clipCount: clips.length,
            pacingScore: this._calculatePacingScore(clips),
        };
    }

    _calculatePacingScore(clips) {
        if (!clips.length) return 0;
        const durations = clips.map((c) => c.duration);
        const avg = durations.reduce((s, v) => s + v, 0) / durations.length;
        const deviation = Math.abs(avg - this.optimalPace);
        return Math.max(0, 100 - deviation * 10);
    }
}

// ═══════════════════════════════════════════════════════
// CLIP SCORER
// ═══════════════════════════════════════════════════════

class ClipScorer {
    scoreClip(clip, analyses) {
        const clipAnalyses = analyses.filter((a) => clip.timeRange.contains(a.timestamp));
        if (!clipAnalyses.length) return QualityScore.zero();

        let score = 0;
        const avgExcitement = clipAnalyses.reduce((s, a) => s + a.excitementScore, 0) / clipAnalyses.length;
        score += Math.min(50, avgExcitement * 1.0);

        const duration = clip.duration;
        if (duration >= 5 && duration <= 10) score += 20;
        else if (duration >= 3 && duration <= 15) score += 10;

        const killCount = clipAnalyses.filter((a) => a.killLog).length;
        const actionDensity = duration > 0 ? killCount / duration : 0;
        score += Math.min(30, actionDensity * 100);

        return new QualityScore(Math.min(100, score), {
            excitement: Math.min(50, avgExcitement * 1.0),
            duration: duration >= 5 && duration <= 10 ? 20 : (duration >= 3 && duration <= 15 ? 10 : 0),
            actionDensity: Math.min(30, actionDensity * 100),
        });
    }

    predictEngagement(clips, analyses) {
        if (!clips.length) return { overallScore: 0, retentionPrediction: 0, clickThroughRate: 0, watchTimeMinutes: 0 };

        const excitementScores = analyses.filter((a) => a.excitementScore > 0).map((a) => a.excitementScore);
        const avgExcitement = excitementScores.length ? excitementScores.reduce((s, v) => s + v, 0) / excitementScores.length : 0;

        const clipLengths = clips.map((c) => c.duration);
        const varietyScore = clipLengths.length > 1 ? _stdev(clipLengths) : 0;

        const clipTypes = new Set(clips.filter((c) => c.clipType).map((c) => c.clipType));
        const diversityBonus = Math.min(15, clipTypes.size * 5);
        const totalDuration = clipLengths.reduce((s, v) => s + v, 0);

        return {
            overallScore: Math.min(100, Math.round(avgExcitement * 1.5 + varietyScore * 5 + diversityBonus)),
            retentionPrediction: avgExcitement > 0 ? Math.min(100, Math.round((avgExcitement / 50) * 100)) : 0,
            clickThroughRate: Math.min(15, Math.round(avgExcitement / 5)),
            watchTimeMinutes: totalDuration / 60,
        };
    }

    suggestImprovements(clips, analyses) {
        const suggestions = [];
        const totalDuration = clips.reduce((s, c) => s + c.duration, 0);

        if (totalDuration > 300) suggestions.push('Video is too long. Consider trimming to 3-5 minutes.');
        if (clips.length > 15) suggestions.push('Too many clips. Focus on the best highlights only.');
        if (totalDuration < 30) suggestions.push('Video is very short. Consider including more clips.');

        const lowClips = clips.filter((c) => c.score.value < 30).length;
        if (lowClips > clips.length * 0.3) {
            suggestions.push('Many low-scoring clips detected. Consider raising the quality threshold.');
        }

        const clipTypes = new Set(clips.filter((c) => c.clipType).map((c) => c.clipType));
        if (clipTypes.size < 2 && clips.length > 3) {
            suggestions.push('Low clip variety. Mix different highlight types for better pacing.');
        }

        return suggestions;
    }
}

// ═══════════════════════════════════════════════════════
// CREATIVE DIRECTOR (Orchestrator)
// ═══════════════════════════════════════════════════════

class CreativeDirector {
    constructor(config = {}) {
        this._config = {
            minClipLength: config.minClipLength || 3,
            maxClipLength: config.maxClipLength || 15,
            targetDuration: config.targetDuration || 180,
            pacingVariation: config.pacingVariation || 0.5,
        };
        this._highlightDetector = new HighlightDetector();
        this._compositionPlanner = new CompositionPlanner({
            targetDuration: this._config.targetDuration,
            minClipLength: this._config.minClipLength,
            maxClipLength: this._config.maxClipLength,
            optimalPace: this._config.pacingVariation * 10,
        });
        this._clipScorer = new ClipScorer();
    }

    direct(analyses) {
        // 1. Excitement analysis
        const enhanced = this._highlightDetector.analyzeExcitementLevels(analyses);
        const multiEvents = this._highlightDetector.detectMultiEvents(enhanced);
        const clutchMoments = this._highlightDetector.detectClutchMoments(enhanced);
        const momentumShifts = this._highlightDetector.analyzeMomentumShifts(enhanced);

        // 2. Suggest highlights
        const highlights = this._highlightDetector.suggestHighlights(enhanced, multiEvents, clutchMoments);

        // 3. Optimize composition
        const optimized = this._compositionPlanner.optimizeClips(highlights, enhanced);

        // 4. Hook intro
        const hookClip = this._compositionPlanner.createHookIntro(optimized);

        // 5. Engagement analysis
        const engagementCurve = this._compositionPlanner.analyzeEngagementCurve(optimized);
        const varietyAnalysis = this._highlightDetector.analyzeVariety(optimized);
        const suggestions = this._clipScorer.suggestImprovements(optimized, enhanced);

        return {
            clips: optimized,
            hookClip,
            engagementCurve,
            varietyAnalysis,
            suggestions,
            multiEvents,
            clutchMoments,
            momentumShifts,
        };
    }
}

// ═══════════════════════════════════════════════════════
// MATH HELPERS
// ═══════════════════════════════════════════════════════

function _variance(arr) {
    if (arr.length < 2) return 0;
    const mean = arr.reduce((s, v) => s + v, 0) / arr.length;
    return arr.reduce((s, v) => s + (v - mean) ** 2, 0) / (arr.length - 1);
}

function _stdev(arr) {
    return Math.sqrt(_variance(arr));
}
