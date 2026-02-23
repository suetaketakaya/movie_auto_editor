// ClipMontage — Video Assembler (ffmpeg.wasm)
// Extracts and concatenates clips using -c copy (no re-encoding)

class VideoAssembler {
    constructor() {
        this._ffmpeg = null;
        this._loaded = false;
        this._cancelled = false;
    }

    cancel() { this._cancelled = true; }

    async load(onLog) {
        if (this._loaded) return;

        const { FFmpeg } = await import('https://cdn.jsdelivr.net/npm/@ffmpeg/ffmpeg@0.12.10/dist/esm/index.js');
        const { toBlobURL } = await import('https://cdn.jsdelivr.net/npm/@ffmpeg/util@0.12.1/dist/esm/index.js');

        this._ffmpeg = new FFmpeg();

        if (onLog) {
            this._ffmpeg.on('log', ({ message }) => onLog(message));
        }

        const coreURL = await toBlobURL(
            'https://cdn.jsdelivr.net/npm/@ffmpeg/core@0.12.6/dist/esm/ffmpeg-core.js',
            'text/javascript',
        );
        const wasmURL = await toBlobURL(
            'https://cdn.jsdelivr.net/npm/@ffmpeg/core@0.12.6/dist/esm/ffmpeg-core.wasm',
            'application/wasm',
        );
        const workerURL = await toBlobURL(
            'https://cdn.jsdelivr.net/npm/@ffmpeg/core@0.12.6/dist/esm/ffmpeg-core.worker.js',
            'text/javascript',
        );

        await this._ffmpeg.load({ coreURL, wasmURL, workerURL });
        this._loaded = true;
    }

    async assemble(videoFile, clips, hookClip, onProgress) {
        if (!this._loaded) throw new Error('FFmpeg not loaded. Call load() first.');
        if (!clips.length) throw new Error('No clips to assemble');
        this._cancelled = false;

        const ffmpeg = this._ffmpeg;

        // Write input video to virtual filesystem
        const inputData = new Uint8Array(await videoFile.arrayBuffer());
        const inputExt = this._getExtension(videoFile.name);
        const inputName = `input${inputExt}`;
        await ffmpeg.writeFile(inputName, inputData);

        // Build ordered clip list (hook first if available)
        const orderedClips = [];
        if (hookClip) orderedClips.push(hookClip);
        orderedClips.push(...clips);

        const totalClips = orderedClips.length;
        const clipFiles = [];

        // Extract each clip with -c copy
        for (let i = 0; i < orderedClips.length; i++) {
            if (this._cancelled) throw new Error('Assembly cancelled');

            const clip = orderedClips[i];
            const outFile = `clip_${i}${inputExt}`;
            clipFiles.push(outFile);

            const startTime = clip.start.toFixed(3);
            const duration = clip.duration.toFixed(3);

            await ffmpeg.exec([
                '-ss', startTime,
                '-i', inputName,
                '-t', duration,
                '-c', 'copy',
                '-avoid_negative_ts', 'make_zero',
                '-y',
                outFile,
            ]);

            if (onProgress) {
                onProgress({
                    step: 'extracting',
                    current: i + 1,
                    total: totalClips,
                    percent: Math.round(((i + 1) / totalClips) * 80),
                });
            }
        }

        // Build concat list
        const concatList = clipFiles.map((f) => `file '${f}'`).join('\n');
        await ffmpeg.writeFile('concat.txt', new TextEncoder().encode(concatList));

        if (onProgress) {
            onProgress({ step: 'concatenating', current: totalClips, total: totalClips, percent: 85 });
        }

        // Concatenate
        const outputName = `output${inputExt}`;
        await ffmpeg.exec([
            '-f', 'concat',
            '-safe', '0',
            '-i', 'concat.txt',
            '-c', 'copy',
            '-y',
            outputName,
        ]);

        if (onProgress) {
            onProgress({ step: 'finalizing', current: totalClips, total: totalClips, percent: 95 });
        }

        // Read output
        const outputData = await ffmpeg.readFile(outputName);
        const mimeType = this._getMimeType(inputExt);
        const blob = new Blob([outputData.buffer], { type: mimeType });

        // Cleanup virtual filesystem
        try {
            await ffmpeg.deleteFile(inputName);
            await ffmpeg.deleteFile('concat.txt');
            await ffmpeg.deleteFile(outputName);
            for (const f of clipFiles) {
                await ffmpeg.deleteFile(f);
            }
        } catch (_) { /* ignore cleanup errors */ }

        if (onProgress) {
            onProgress({ step: 'done', current: totalClips, total: totalClips, percent: 100 });
        }

        return blob;
    }

    _getExtension(filename) {
        const dot = filename.lastIndexOf('.');
        return dot >= 0 ? filename.substring(dot).toLowerCase() : '.mp4';
    }

    _getMimeType(ext) {
        const map = {
            '.mp4': 'video/mp4',
            '.webm': 'video/webm',
            '.mkv': 'video/x-matroska',
            '.avi': 'video/x-msvideo',
            '.mov': 'video/quicktime',
        };
        return map[ext] || 'video/mp4';
    }
}
