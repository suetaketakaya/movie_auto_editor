// ClipMontage — Video Assembler (ffmpeg.wasm)
// Supports: -c copy (fast), drawtext overlays, xfade transitions, slow-motion

class VideoAssembler {
    constructor(opts = {}) {
        this._ffmpeg = null;
        this._loaded = false;
        this._cancelled = false;
        // Effect options (set via setEffectOptions before assemble())
        this._effects = {
            transitions: opts.transitions !== false,   // xfade between clips
            textOverlay: opts.textOverlay !== false,   // drawtext kill labels
            slowMo: opts.slowMo !== false,             // 0.5x slow-mo on high-score clips
        };
    }

    setEffectOptions(opts) {
        Object.assign(this._effects, opts);
    }

    cancel() { this._cancelled = true; }

    async load(onLog) {
        if (this._loaded) return;

        const { FFmpeg } = await import('https://cdn.jsdelivr.net/npm/@ffmpeg/ffmpeg@0.12.10/dist/esm/index.js');

        this._ffmpeg = new FFmpeg();
        if (onLog) {
            this._ffmpeg.on('log', ({ message }) => onLog(message));
        }

        // crossOriginIsolated=true (Firebase COEP+COOP) → use multi-thread core (core-mt)
        // crossOriginIsolated=false (local emulator) → use single-thread core (no workerURL)
        // Use CDN URLs directly (no toBlobURL) because:
        //   - ESM worker uses `import("./ffmpeg-core.js")` which fails from blob: base URL
        //   - CSP already allows cdn.jsdelivr.net in script-src and worker-src
        const useMT = self.crossOriginIsolated === true;
        const coreBase = useMT
            ? 'https://cdn.jsdelivr.net/npm/@ffmpeg/core-mt@0.12.6/dist/esm'
            : 'https://cdn.jsdelivr.net/npm/@ffmpeg/core@0.12.6/dist/esm';

        console.log(`[VideoAssembler] crossOriginIsolated=${useMT} → ${useMT ? 'multi-thread' : 'single-thread'} core`);

        const loadOpts = {
            coreURL:  `${coreBase}/ffmpeg-core.js`,
            wasmURL:  `${coreBase}/ffmpeg-core.wasm`,
        };
        if (useMT) {
            loadOpts.workerURL = `${coreBase}/ffmpeg-core.worker.js`;
        }

        await this._ffmpeg.load(loadOpts);
        this._loaded = true;
    }

    /**
     * @param {File} videoFile
     * @param {Clip[]} clips
     * @param {Clip|null} hookClip
     * @param {(p: object) => void} onProgress
     */
    async assemble(videoFile, clips, hookClip, onProgress) {
        if (!this._loaded) throw new Error('FFmpeg not loaded. Call load() first.');
        if (!clips.length) throw new Error('No clips to assemble');
        this._cancelled = false;

        const ffmpeg = this._ffmpeg;
        const inputData = new Uint8Array(await videoFile.arrayBuffer());
        const inputExt = this._getExtension(videoFile.name);
        const inputName = `input${inputExt}`;
        await ffmpeg.writeFile(inputName, inputData);

        const orderedClips = [];
        if (hookClip) orderedClips.push(hookClip);
        orderedClips.push(...clips);

        const totalClips = orderedClips.length;
        const needsReencode = this._effects.transitions || this._effects.textOverlay || this._effects.slowMo;

        // ── Step 1: Extract individual clips ──
        const clipFiles = [];
        for (let i = 0; i < orderedClips.length; i++) {
            if (this._cancelled) throw new Error('Assembly cancelled');

            const clip = orderedClips[i];
            const outFile = `clip_${i}.mp4`; // always mp4 for re-encode path
            clipFiles.push(outFile);

            const startTime = clip.start.toFixed(3);
            const duration = clip.duration.toFixed(3);

            if (needsReencode) {
                // Re-encode with optional effects
                const vfFilters = this._buildVideoFilters(clip, i);
                const args = [
                    '-ss', startTime,
                    '-i', inputName,
                    '-t', duration,
                ];
                if (vfFilters) {
                    args.push('-vf', vfFilters);
                }
                args.push(
                    '-c:v', 'libx264',
                    '-preset', 'ultrafast',
                    '-crf', '23',
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-avoid_negative_ts', 'make_zero',
                    '-y',
                    outFile,
                );
                await ffmpeg.exec(args);
            } else {
                // Fast path: stream copy
                await ffmpeg.exec([
                    '-ss', startTime,
                    '-i', inputName,
                    '-t', duration,
                    '-c', 'copy',
                    '-avoid_negative_ts', 'make_zero',
                    '-y',
                    outFile,
                ]);
            }

            if (onProgress) {
                onProgress({
                    step: 'extracting',
                    current: i + 1,
                    total: totalClips,
                    percent: Math.round(((i + 1) / totalClips) * (needsReencode ? 70 : 80)),
                });
            }
        }

        // ── Step 2: Concatenate (with or without xfade) ──
        let outputName;

        if (needsReencode && this._effects.transitions && clipFiles.length > 1) {
            try {
                outputName = await this._concatWithXfade(clipFiles, orderedClips, onProgress, totalClips);
            } catch (xfadeErr) {
                console.warn('xfade transition failed, falling back to simple concat:', xfadeErr.message);
                outputName = null; // trigger fallback below
            }
        }

        if (!outputName) {
            outputName = `output.mp4`;
            const concatList = clipFiles.map((f) => `file '${f}'`).join('\n');
            await ffmpeg.writeFile('concat.txt', new TextEncoder().encode(concatList));

            if (onProgress) onProgress({ step: 'concatenating', current: totalClips, total: totalClips, percent: 85 });

            await ffmpeg.exec([
                '-f', 'concat',
                '-safe', '0',
                '-i', 'concat.txt',
                '-c', 'copy',
                '-y',
                outputName,
            ]);
        }

        if (onProgress) onProgress({ step: 'finalizing', current: totalClips, total: totalClips, percent: 95 });

        // Read output
        const outputData = await ffmpeg.readFile(outputName);
        const blob = new Blob([outputData.buffer], { type: 'video/mp4' });

        // Cleanup
        try {
            await ffmpeg.deleteFile(inputName);
            for (const f of clipFiles) await ffmpeg.deleteFile(f);
            try { await ffmpeg.deleteFile('concat.txt'); } catch (_) {}
            if (outputName !== 'output.mp4') {
                try { await ffmpeg.deleteFile(outputName); } catch (_) {}
            } else {
                try { await ffmpeg.deleteFile('output.mp4'); } catch (_) {}
            }
        } catch (_) {}

        if (onProgress) onProgress({ step: 'done', current: totalClips, total: totalClips, percent: 100 });

        return blob;
    }

    // ── Private helpers ──

    /**
     * Build -vf filter string for a clip.
     * Applies: slow-mo (high-score clips), drawtext overlay.
     */
    _buildVideoFilters(clip, index) {
        const filters = [];

        // Slow-mo: setpts=2.0 for high-score clips (QualityScore.value >= 80)
        const scoreValue = clip.score && typeof clip.score === 'object'
            ? (clip.score.value ?? 0)
            : (typeof clip.score === 'number' ? clip.score : 0);
        if (this._effects.slowMo && scoreValue >= 80) {
            filters.push('setpts=2.0*PTS');
        }

        // Text overlay: use clip.label set by CreativeDirector (e.g. 'ACE', 'CLUTCH', 'TRIPLE KILL')
        if (this._effects.textOverlay) {
            const label = this._getClipLabel(clip);
            if (label) {
                // Escape for ffmpeg drawtext: colon, backslash, single-quote
                const safeLabel = label.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/:/g, '\\:');
                filters.push(
                    `drawtext=text='${safeLabel}':` +
                    `fontsize=48:fontcolor=white:x=(w-text_w)/2:y=h-80:` +
                    `box=1:boxcolor=black@0.5:boxborderw=8:` +
                    `enable='lt(t,1.5)'`
                );
            }
        }

        return filters.length > 0 ? filters.join(',') : null;
    }

    _getClipLabel(clip) {
        if (!clip) return null;
        // clip.label is set by CreativeDirector: 'ACE', 'CLUTCH', 'TRIPLE KILL', 'INTENSE', 'HOOK', etc.
        const label = clip.label || '';
        if (!label || label === 'INTENSE' || label === 'HOOK') return null; // skip generic labels
        return label;
    }

    /**
     * Concatenate clips with xfade transitions between each pair.
     * Uses the complex filtergraph approach.
     */
    async _concatWithXfade(clipFiles, clips, onProgress, totalClips) {
        const ffmpeg = this._ffmpeg;
        const transitionDuration = 0.3;
        const transitionType = 'fade';
        const outputName = 'output_xfade.mp4';

        if (onProgress) onProgress({ step: 'concatenating', current: totalClips, total: totalClips, percent: 75 });

        if (clipFiles.length === 1) {
            // Single clip — just rename
            await ffmpeg.exec(['-i', clipFiles[0], '-c', 'copy', '-y', outputName]);
            return outputName;
        }

        // Build xfade filtergraph
        // Each clip's offset = sum of previous clip durations minus accumulated transition time
        let offset = 0;
        const inputs = clipFiles.map((f) => ['-i', f]).flat();
        const filterParts = [];
        let lastVideo = `[0:v]`;
        let lastAudio = `[0:a]`;

        for (let i = 1; i < clipFiles.length; i++) {
            // Compute xfade offset: start of this transition in the merged timeline
            offset += clips[i - 1].duration - transitionDuration;

            const outV = i === clipFiles.length - 1 ? '[vout]' : `[v${i}]`;
            const outA = i === clipFiles.length - 1 ? '[aout]' : `[a${i}]`;

            filterParts.push(
                `${lastVideo}[${i}:v]xfade=transition=${transitionType}:duration=${transitionDuration}:offset=${offset.toFixed(3)}${outV}`
            );
            filterParts.push(
                `${lastAudio}[${i}:a]acrossfade=d=${transitionDuration}${outA}`
            );

            lastVideo = outV;
            lastAudio = outA;
        }

        const filterComplex = filterParts.join(';');

        await ffmpeg.exec([
            ...inputs,
            '-filter_complex', filterComplex,
            '-map', '[vout]',
            '-map', '[aout]',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-y',
            outputName,
        ]);

        return outputName;
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
