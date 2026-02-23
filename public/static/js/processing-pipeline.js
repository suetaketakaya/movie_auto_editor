// ClipMontage — Processing Pipeline (Orchestrator)
// Integrates: FrameExtractor -> HuggingFaceClient -> CreativeDirector -> VideoAssembler

class ProcessingPipeline {
    constructor(opts = {}) {
        this._apiKey = opts.apiKey;
        this._onProgress = opts.onProgress || (() => {});
        this._onLog = opts.onLog || (() => {});
        this._onComplete = opts.onComplete || (() => {});
        this._onError = opts.onError || (() => {});

        this._frameExtractor = new FrameExtractor();
        this._visionClient = null;
        this._creativeDirector = new CreativeDirector();
        this._videoAssembler = new VideoAssembler();

        this._cancelled = false;
        this._resultBlob = null;
        this._resultStats = null;
    }

    cancel() {
        this._cancelled = true;
        this._frameExtractor.cancel();
        if (this._visionClient) this._visionClient.cancel();
        this._videoAssembler.cancel();
    }

    get resultBlob() { return this._resultBlob; }
    get resultStats() { return this._resultStats; }

    async run(file) {
        this._cancelled = false;
        this._resultBlob = null;
        this._resultStats = null;
        const startTime = Date.now();

        try {
            // Validate API key
            if (!this._apiKey) {
                throw new Error('HuggingFace API token is required. Please set it in Settings.');
            }
            this._visionClient = new HuggingFaceClient(this._apiKey);

            // ── Step 1: Frame Extraction (0-25%) ──
            this._updateProgress('frame_extraction', 0, 'Extracting frames...');
            this._log('Starting frame extraction...');

            const { frames, videoInfo } = await this._frameExtractor.extractFrames(file, (p) => {
                const overall = Math.round(p.percent * 0.25);
                this._updateProgress('frame_extraction', overall, `Extracting frame ${p.current}/${p.total} (${p.timestamp.toFixed(1)}s)`);
            });

            if (this._cancelled) throw new Error('Cancelled');
            this._log(`Extracted ${frames.length} frames from ${videoInfo.durationFormatted} video`);

            if (frames.length === 0) {
                throw new Error('No frames could be extracted from the video');
            }

            // ── Step 2: HuggingFace AI Analysis (25-60%) ──
            this._updateProgress('ai_analysis', 25, 'Starting AI analysis...');
            this._log('Analyzing frames with HuggingFace Vision AI...');

            const analyses = await this._visionClient.analyzeFramesBatch(frames, (p) => {
                const overall = 25 + Math.round(p.percent * 0.35);
                this._updateProgress('ai_analysis', overall, `Analyzing frame ${p.current}/${p.total}`);
            });

            if (this._cancelled) throw new Error('Cancelled');

            const validAnalyses = analyses.filter((a) => !a.metadata?.error);
            const failedAnalyses = analyses.filter((a) => a.metadata?.error);
            this._log(`AI analysis complete: ${validAnalyses.length}/${frames.length} frames analyzed successfully`);

            if (failedAnalyses.length > 0) {
                const firstError = failedAnalyses[0].metadata.error;
                this._log(`First analysis error: ${firstError}`);
            }

            if (validAnalyses.length === 0) {
                const firstError = failedAnalyses.length > 0 ? failedAnalyses[0].metadata.error : 'Unknown error';
                throw new Error(`All frame analyses failed. API error: ${firstError}`);
            }

            // ── Step 3: Highlight Detection & Composition (60-75%) ──
            this._updateProgress('clip_detection', 60, 'Detecting highlights...');
            this._log('Running creative direction pipeline...');

            const directorResult = this._creativeDirector.direct(validAnalyses);

            if (this._cancelled) throw new Error('Cancelled');

            this._updateProgress('clip_detection', 70, `Found ${directorResult.clips.length} highlight clips`);
            this._log(`Creative direction complete: ${directorResult.clips.length} clips, ` +
                `${directorResult.multiEvents.length} multi-events, ` +
                `${directorResult.clutchMoments.length} clutch moments`);

            if (directorResult.clips.length === 0) {
                throw new Error('No highlights detected in the video. Try with more action-packed footage.');
            }

            // Clamp clip ranges to video duration
            const clampedClips = directorResult.clips.map((c) => {
                const endClamped = Math.min(c.end, videoInfo.duration);
                const startClamped = Math.min(c.start, endClamped - 0.1);
                if (endClamped - startClamped < 0.5) return null;
                return c.withAdjustedRange(new TimeRange(Math.max(0, startClamped), endClamped));
            }).filter(Boolean);

            let hookClip = directorResult.hookClip;
            if (hookClip) {
                const hookEnd = Math.min(hookClip.end, videoInfo.duration);
                const hookStart = Math.min(hookClip.start, hookEnd - 0.1);
                if (hookEnd - hookStart < 0.5) {
                    hookClip = null;
                } else {
                    hookClip = hookClip.withAdjustedRange(new TimeRange(Math.max(0, hookStart), hookEnd));
                }
            }

            this._updateProgress('clip_detection', 75, 'Highlights selected');

            // ── Step 4: Video Generation (75-100%) ──
            this._updateProgress('video_generation', 75, 'Loading ffmpeg.wasm...');
            this._log('Loading ffmpeg.wasm...');

            await this._videoAssembler.load((msg) => this._log(`[ffmpeg] ${msg}`));

            if (this._cancelled) throw new Error('Cancelled');

            this._updateProgress('video_generation', 78, 'Assembling video...');
            this._log(`Assembling ${clampedClips.length} clips${hookClip ? ' + hook intro' : ''}...`);

            const outputBlob = await this._videoAssembler.assemble(file, clampedClips, hookClip, (p) => {
                const overall = 75 + Math.round(p.percent * 0.25);
                this._updateProgress('video_generation', overall, `${p.step}: clip ${p.current}/${p.total}`);
            });

            if (this._cancelled) throw new Error('Cancelled');

            // Calculate final stats
            const totalDuration = clampedClips.reduce((s, c) => s + c.duration, 0) + (hookClip ? hookClip.duration : 0);
            const clipScorer = new ClipScorer();
            const engagement = clipScorer.predictEngagement(clampedClips, validAnalyses);
            const qualityScore = engagement.overallScore;

            this._resultBlob = outputBlob;
            this._resultStats = {
                clipCount: clampedClips.length + (hookClip ? 1 : 0),
                totalDuration,
                qualityScore,
                outputSize: outputBlob.size,
                processingTime: ((Date.now() - startTime) / 1000).toFixed(1),
                suggestions: directorResult.suggestions,
                warnings: this._generateWarnings(directorResult, clampedClips),
                engagement,
                varietyAnalysis: directorResult.varietyAnalysis,
            };

            this._updateProgress('completed', 100, 'Processing complete!');
            this._log(`Processing complete! Output: ${this._formatSize(outputBlob.size)}, Duration: ${totalDuration.toFixed(1)}s`);
            this._onComplete(this._resultBlob, this._resultStats);

        } catch (err) {
            const msg = (err && err.message) ? err.message : String(err || 'Unknown error');
            if (msg === 'Cancelled' || msg.includes('cancelled')) {
                this._log('Processing cancelled by user');
                return;
            }
            this._log(`Error: ${msg}`);
            this._onError(msg);
        }
    }

    _updateProgress(stage, percent, message) {
        this._onProgress({ type: 'progress', stage, progress: percent, message });
    }

    _log(message) {
        this._onLog(message);
    }

    _generateWarnings(directorResult, clips) {
        const warnings = [];
        if (clips.length < 3) warnings.push('Few highlight clips detected. Video quality may be limited.');
        if (directorResult.varietyAnalysis?.issues?.includes('low_type_variety')) {
            warnings.push('Low clip variety detected. Mix of highlight types could improve engagement.');
        }
        if (directorResult.varietyAnalysis?.issues?.includes('uniform_clip_lengths')) {
            warnings.push('Clips have similar durations. Varied lengths improve pacing.');
        }
        return warnings;
    }

    _formatSize(bytes) {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }
}
