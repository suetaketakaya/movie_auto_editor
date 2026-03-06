// ClipMontage — Browser Frame Extractor (Video + Canvas API)
// Supports adaptive sampling driven by AudioEnergyData when provided.

class FrameExtractor {
    constructor(opts = {}) {
        this.intervalSeconds = opts.intervalSeconds || 10;
        this.maxFrames = opts.maxFrames || 60;
        this.jpegQuality = opts.jpegQuality || 0.85;
        this.maxWidth = opts.maxWidth || 1280;
        this._cancelled = false;
    }

    cancel() { this._cancelled = true; }

    /**
     * Extract frames from a video file.
     * @param {File} file
     * @param {(p: object) => void} onProgress
     * @param {AudioEnergyData} [audioEnergy] — optional, enables adaptive sampling
     */
    async extractFrames(file, onProgress, audioEnergy) {
        this._cancelled = false;
        const videoUrl = URL.createObjectURL(file);

        try {
            const video = document.createElement('video');
            video.muted = true;
            video.preload = 'auto';

            await new Promise((resolve, reject) => {
                video.onloadedmetadata = resolve;
                video.onerror = () => reject(new Error('Failed to load video'));
                video.src = videoUrl;
            });

            // Wait for enough data to seek
            await new Promise((resolve) => {
                if (video.readyState >= 3) { resolve(); return; }
                video.oncanplaythrough = resolve;
                setTimeout(resolve, 3000);
            });

            const duration = video.duration;
            if (!duration || !isFinite(duration)) {
                throw new Error('Cannot determine video duration');
            }

            const videoInfo = {
                duration,
                width: video.videoWidth,
                height: video.videoHeight,
                durationFormatted: `${Math.floor(duration / 60)}:${String(Math.floor(duration % 60)).padStart(2, '0')}`,
            };

            // Canvas setup
            let canvasW = video.videoWidth;
            let canvasH = video.videoHeight;
            if (canvasW > this.maxWidth) {
                const ratio = this.maxWidth / canvasW;
                canvasW = this.maxWidth;
                canvasH = Math.round(canvasH * ratio);
            }
            const canvas = document.createElement('canvas');
            canvas.width = canvasW;
            canvas.height = canvasH;
            const ctx = canvas.getContext('2d');

            // Build sample timestamps — adaptive or uniform
            const timestamps = this._buildTimestamps(duration, audioEnergy);
            const totalFrames = timestamps.length;

            if (audioEnergy && !audioEnergy.isEmpty) {
                const peaks = audioEnergy.getPeakTimestamps().length;
                console.log(
                    `FrameExtractor: adaptive sampling — ${totalFrames} frames ` +
                    `(${peaks} peak-guided, audio-driven)`,
                );
            }

            const frames = [];

            for (let i = 0; i < totalFrames; i++) {
                if (this._cancelled) throw new Error('Frame extraction cancelled');

                const timestamp = timestamps[i];
                if (timestamp >= duration) continue;

                // Seek (with 15s timeout to prevent infinite hang on broken seek)
                video.currentTime = timestamp;
                await Promise.race([
                    new Promise((resolve, reject) => {
                        const onSeeked = () => {
                            video.removeEventListener('seeked', onSeeked);
                            video.removeEventListener('error', onError);
                            resolve();
                        };
                        const onError = () => {
                            video.removeEventListener('seeked', onSeeked);
                            video.removeEventListener('error', onError);
                            reject(new Error(`Seek failed at ${timestamp}s`));
                        };
                        video.addEventListener('seeked', onSeeked);
                        video.addEventListener('error', onError);
                    }),
                    new Promise((_, reject) =>
                        setTimeout(() => reject(new Error(`Seek timeout at ${timestamp}s`)), 15000)
                    ),
                ]);

                ctx.drawImage(video, 0, 0, canvasW, canvasH);
                const blob = await new Promise((resolve, reject) => {
                    canvas.toBlob(
                        (b) => b ? resolve(b) : reject(new Error(`toBlob returned null at ${timestamp}s`)),
                        'image/jpeg',
                        this.jpegQuality
                    );
                });

                frames.push({ timestamp, blob });

                if (onProgress) {
                    onProgress({
                        current: i + 1,
                        total: totalFrames,
                        percent: Math.round(((i + 1) / totalFrames) * 100),
                        timestamp,
                    });
                }
            }

            return { frames, videoInfo };
        } finally {
            URL.revokeObjectURL(videoUrl);
        }
    }

    // ── Private ──

    _buildTimestamps(duration, audioEnergy) {
        if (audioEnergy && !audioEnergy.isEmpty) {
            return audioEnergy.buildSampleTimestamps(duration, {
                denseSec: 2,
                sparseSec: 20,
                maxFrames: this.maxFrames,
            });
        }

        // Uniform fallback
        const total = Math.min(
            this.maxFrames,
            Math.floor(duration / this.intervalSeconds) + 1,
        );
        const timestamps = [];
        for (let i = 0; i < total; i++) {
            const t = i * this.intervalSeconds;
            if (t > duration) break;
            timestamps.push(t);
        }
        return timestamps;
    }
}
