// ClipMontage — Data Models (JS port of Python domain entities/value objects)

class TimeRange {
    constructor(startSeconds, endSeconds) {
        this.startSeconds = Math.max(0, startSeconds);
        this.endSeconds = endSeconds;
        if (this.endSeconds <= this.startSeconds) {
            throw new Error(`endSeconds (${this.endSeconds}) must be > startSeconds (${this.startSeconds})`);
        }
    }

    get duration() { return this.endSeconds - this.startSeconds; }
    get midpoint() { return (this.startSeconds + this.endSeconds) / 2; }

    overlaps(other) {
        return this.startSeconds < other.endSeconds && other.startSeconds < this.endSeconds;
    }

    contains(timestamp) {
        return this.startSeconds <= timestamp && timestamp <= this.endSeconds;
    }

    merge(other) {
        if (!this.overlaps(other)) throw new Error('Cannot merge non-overlapping ranges');
        return new TimeRange(
            Math.min(this.startSeconds, other.startSeconds),
            Math.max(this.endSeconds, other.endSeconds),
        );
    }

    extend(before = 0, after = 0) {
        return new TimeRange(
            Math.max(0, this.startSeconds - before),
            this.endSeconds + after,
        );
    }
}

class QualityScore {
    constructor(value, breakdown = {}) {
        this.value = Math.max(0, Math.min(100, value));
        this.breakdown = breakdown;
    }

    get isAcceptable() { return this.value >= 70; }

    get grade() {
        if (this.value >= 90) return 'A';
        if (this.value >= 80) return 'B';
        if (this.value >= 70) return 'C';
        if (this.value >= 60) return 'D';
        return 'F';
    }

    static fromComponents(weights, scores) {
        const totalWeight = Object.values(weights).reduce((s, v) => s + v, 0);
        if (totalWeight === 0) return new QualityScore(0);
        let weightedSum = 0;
        for (const k of Object.keys(weights)) {
            weightedSum += (weights[k] || 0) * (scores[k] || 0);
        }
        return new QualityScore(weightedSum / totalWeight, scores);
    }

    withBonus(bonus, reason = '') {
        const bd = { ...this.breakdown };
        if (reason) bd[reason] = bonus;
        return new QualityScore(this.value + bonus, bd);
    }

    static zero() { return new QualityScore(0); }
    static perfect() { return new QualityScore(100); }
}

class FrameAnalysis {
    constructor(opts = {}) {
        this.framePath = opts.framePath || '';
        this.timestamp = opts.timestamp || 0;
        this.killLog = opts.killLog || false;
        this.matchStatus = opts.matchStatus || 'unknown';
        this.actionIntensity = opts.actionIntensity || 'low';
        this.enemyVisible = opts.enemyVisible || false;
        this.sceneDescription = opts.sceneDescription || '';
        this.confidence = opts.confidence || 0;
        this.excitementScore = opts.excitementScore || 0;
        this.modelUsed = opts.modelUsed || '';
        this.rawResponse = opts.rawResponse || null;
        this.uiElements = opts.uiElements || '';
        this.metadata = opts.metadata || {};
        this.killCount = opts.killCount || 0;
        this.enemyCount = opts.enemyCount || 0;
        this.visualQuality = opts.visualQuality || 'normal';
    }

    toLegacyDict() {
        return {
            frame_path: this.framePath,
            timestamp: this.timestamp,
            kill_log: this.killLog,
            match_status: this.matchStatus,
            action_intensity: this.actionIntensity,
            enemy_visible: this.enemyVisible,
            scene_description: this.sceneDescription,
            confidence: this.confidence,
            excitement_score: this.excitementScore,
            kill_count: this.killCount,
            enemy_count: this.enemyCount,
            visual_quality: this.visualQuality,
        };
    }

    static fromApiResponse(parsed, timestamp, imageBlob, modelUsed = 'unknown') {
        return new FrameAnalysis({
            timestamp,
            killLog: !!parsed.kill_log,
            matchStatus: String(parsed.match_status || 'unknown'),
            actionIntensity: String(parsed.action_intensity || 'low'),
            enemyVisible: !!parsed.enemy_visible,
            sceneDescription: String(parsed.scene_description || ''),
            confidence: Number(parsed.confidence || 0),
            uiElements: String(parsed.ui_elements || ''),
            killCount: parseInt(parsed.kill_count, 10) || 0,
            enemyCount: parseInt(parsed.enemy_count, 10) || 0,
            visualQuality: String(parsed.visual_quality || 'normal'),
            modelUsed,
        });
    }
}

class Clip {
    constructor(opts = {}) {
        this.timeRange = opts.timeRange;
        this.reason = opts.reason || '';
        this.score = opts.score || QualityScore.zero();
        this.clipType = opts.clipType || '';
        this.label = opts.label || '';
        this.priority = opts.priority || 0;
        this.actionIntensity = opts.actionIntensity || 'low';
        this.id = opts.id || crypto.randomUUID();
        this.metadata = opts.metadata || {};
    }

    get duration() { return this.timeRange.duration; }
    get start() { return this.timeRange.startSeconds; }
    get end() { return this.timeRange.endSeconds; }

    withAdjustedRange(newRange) {
        return new Clip({
            timeRange: newRange,
            reason: this.reason,
            score: this.score,
            clipType: this.clipType,
            label: this.label,
            priority: this.priority,
            actionIntensity: this.actionIntensity,
            id: this.id,
            metadata: this.metadata,
        });
    }

    withScore(newScore) {
        return new Clip({
            timeRange: this.timeRange,
            reason: this.reason,
            score: newScore,
            clipType: this.clipType,
            label: this.label,
            priority: this.priority,
            actionIntensity: this.actionIntensity,
            id: this.id,
            metadata: this.metadata,
        });
    }
}
