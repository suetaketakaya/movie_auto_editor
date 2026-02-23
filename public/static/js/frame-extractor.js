// ClipMontage — Browser Frame Extractor (Video + Canvas API)
// Replaces backend OpenCV frame extraction

class FrameExtractor {
    constructor(opts = {}) {
        this.intervalSeconds = opts.intervalSeconds || 10;
        this.maxFrames = opts.maxFrames || 60;
        this.jpegQuality = opts.jpegQuality || 0.85;
        this.maxWidth = opts.maxWidth || 1280;
        this._cancelled = false;
    }

    cancel() { this._cancelled = true; }

    async extractFrames(file, onProgress) {
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
                // Fallback timeout
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

            // Calculate scale for canvas
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

            const totalFrames = Math.min(
                this.maxFrames,
                Math.floor(duration / this.intervalSeconds) + 1,
            );

            const frames = [];

            for (let i = 0; i < totalFrames; i++) {
                if (this._cancelled) throw new Error('Frame extraction cancelled');

                const timestamp = i * this.intervalSeconds;
                if (timestamp > duration) break;

                // Seek to timestamp
                video.currentTime = timestamp;
                await new Promise((resolve, reject) => {
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
                });

                // Draw frame to canvas
                ctx.drawImage(video, 0, 0, canvasW, canvasH);

                // Convert to JPEG blob
                const blob = await new Promise((resolve) => {
                    canvas.toBlob(resolve, 'image/jpeg', this.jpegQuality);
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
}
