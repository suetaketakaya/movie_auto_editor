// ClipMontage — Processing Pipeline (Orchestrator)
// Stages: Audio Analysis → Frame Extraction → Vision AI → Creative Direction → Video Assembly

class ProcessingPipeline {
    constructor(opts = {}) {
        this._providerSettings = opts.providerSettings || null;
        // Legacy: support bare apiKey (treated as HuggingFace)
        if (!this._providerSettings && opts.apiKey) {
            this._providerSettings = { provider: 'huggingface', apiKey: opts.apiKey };
        }

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
            // Build vision provider
            const settings = this._providerSettings || VisionProviderFactory.loadSettings();
            if (!settings.apiKey && settings.provider !== 'ollama') {
                throw new Error(
                    `No API key configured for ${settings.provider}. ` +
                    'Please set your API key in Settings.'
                );
            }
            this._visionClient = VisionProviderFactory.create(settings);

            // ── Stage 0: Audio Analysis (0-10%) ──
            this._updateProgress('audio_analysis', 0, 'Analyzing audio energy...');
            this._log('Analyzing audio for peak detection...');

            let audioEnergy;
            try {
                audioEnergy = await AudioAnalyzer.analyze(file, {
                    onProgress: (pct) => {
                        this._updateProgress('audio_analysis', Math.round(pct * 0.10), 'Analyzing audio...');
                    },
                });
                const peakCount = audioEnergy.getPeakTimestamps().length;
                this._log(`Audio analysis complete: ${peakCount} high-energy seconds detected`);
            } catch (err) {
                this._log(`Audio analysis skipped: ${err.message}`);
                audioEnergy = new AudioEnergyData([], 0);
            }

            if (this._cancelled) throw new Error('Cancelled');

            // ── Stage 1: Frame Extraction (10-30%) ──
            this._updateProgress('frame_extraction', 10, 'Extracting frames...');
            this._log('Starting frame extraction...');

            const { frames, videoInfo } = await this._frameExtractor.extractFrames(
                file,
                (p) => {
                    const overall = 10 + Math.round(p.percent * 0.20);
                    this._updateProgress('frame_extraction', overall, `Extracting frame ${p.current}/${p.total} (${p.timestamp.toFixed(1)}s)`);
                },
                audioEnergy,
            );

            if (this._cancelled) throw new Error('Cancelled');
            this._log(`Extracted ${frames.length} frames from ${videoInfo.durationFormatted} video`);

            if (frames.length === 0) {
                throw new Error('No frames could be extracted from the video');
            }

            // ── Stage 2: Vision AI Analysis (30-65%) ──
            const providerLabel = (settings.provider || 'huggingface').toUpperCase();
            this._updateProgress('ai_analysis', 30, `Starting AI analysis (${providerLabel})...`);
            this._log(`Analyzing frames with ${providerLabel} Vision AI...`);

            const analyses = await this._visionClient.analyzeFramesBatch(frames, (p) => {
                const overall = 30 + Math.round(p.percent * 0.35);
                this._updateProgress('ai_analysis', overall, `Analyzing frame ${p.current}/${p.total}`);
            });

            if (this._cancelled) throw new Error('Cancelled');

            const validAnalyses = analyses.filter((a) => !a.metadata?.error);
            const failedAnalyses = analyses.filter((a) => a.metadata?.error);
            this._log(`AI analysis complete: ${validAnalyses.length}/${frames.length} frames analyzed successfully`);

            if (failedAnalyses.length > 0) {
                this._log(`First analysis error: ${failedAnalyses[0].metadata.error}`);
            }

            if (validAnalyses.length === 0) {
                const firstError = failedAnalyses.length > 0 ? failedAnalyses[0].metadata.error : 'Unknown error';
                throw new Error(`All frame analyses failed. API error: ${firstError}`);
            }

            // ── Stage 3: Highlight Detection (65-77%) ──
            this._updateProgress('clip_detection', 65, 'Detecting highlights...');
            this._log('Running creative direction pipeline...');

            const directorResult = this._creativeDirector.direct(validAnalyses);

            if (this._cancelled) throw new Error('Cancelled');

            this._updateProgress('clip_detection', 72, `Found ${directorResult.clips.length} highlight clips`);
            this._log(
                `Creative direction complete: ${directorResult.clips.length} clips, ` +
                `${directorResult.multiEvents.length} multi-events, ` +
                `${directorResult.clutchMoments.length} clutch moments`
            );

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

            this._updateProgress('clip_detection', 77, 'Highlights selected');

            // ── Stage 4: Video Generation (77-100%) ──
            this._updateProgress('video_generation', 77, 'Loading ffmpeg.wasm...');
            this._log('Loading ffmpeg.wasm...');

            // Configure effects
            const effectsEnabled = this._getEffectsSettings();
            this._videoAssembler.setEffectOptions(effectsEnabled);
            const effectsList = Object.entries(effectsEnabled)
                .filter(([, v]) => v)
                .map(([k]) => k)
                .join(', ');
            this._log(`Effects enabled: ${effectsList || 'none (fast copy mode)'}`);

            await this._videoAssembler.load((msg) => this._log(`[ffmpeg] ${msg}`));

            if (this._cancelled) throw new Error('Cancelled');

            this._updateProgress('video_generation', 80, 'Assembling video...');
            this._log(`Assembling ${clampedClips.length} clips${hookClip ? ' + hook intro' : ''}...`);

            const outputBlob = await this._videoAssembler.assemble(file, clampedClips, hookClip, (p) => {
                const overall = 80 + Math.round(p.percent * 0.20);
                this._updateProgress('video_generation', overall, `${p.step}: clip ${p.current}/${p.total}`);
            });

            if (this._cancelled) throw new Error('Cancelled');

            // Stats
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
                provider: settings.provider,
                audioEnergySecs: audioEnergy.getPeakTimestamps().length,
            };

            this._updateProgress('completed', 100, 'Processing complete!');
            this._log(`Processing complete! Output: ${this._formatSize(outputBlob.size)}, Duration: ${totalDuration.toFixed(1)}s`);
            this._onComplete(this._resultBlob, this._resultStats);

        } catch (err) {
            const msg = (err && err.message) ? err.message : String(err || 'Unknown error');
            if (msg === 'Cancelled' || msg.toLowerCase().includes('cancelled')) {
                this._log('Processing cancelled by user');
                return;
            }
            this._log(`Error: ${msg}`);
            this._onError(msg);
        }
    }

    _getEffectsSettings() {
        return {
            transitions: sessionStorage.getItem('effect_transitions') !== 'false',
            textOverlay: sessionStorage.getItem('effect_textOverlay') !== 'false',
            slowMo: sessionStorage.getItem('effect_slowMo') !== 'false',
        };
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
