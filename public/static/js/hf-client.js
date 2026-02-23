// ClipMontage — Browser HuggingFace Inference API Client
// Multi-model fallback with automatic rate-limit rotation

class HuggingFaceClient {
    constructor(apiKey) {
        if (!apiKey) throw new Error('HuggingFace API token is required');
        this._apiKey = apiKey;
        this._models = [
            'Qwen/Qwen2.5-VL-7B-Instruct',
            'meta-llama/Llama-3.2-11B-Vision-Instruct',
            'mistralai/Mistral-Small-3.1-24B-Instruct-2503',
        ];
        this._currentModelIndex = 0;
        this._baseUrl = 'https://router.huggingface.co/api/inference-endpoints/models';
        this._maxRetries = 3;
        this._initialBackoff = 2000;
        this._concurrency = 1;
        this._requestDelay = 2000;
        this._coldStartTimeout = 120000;   // 120s for cold-start models
        this._coldStartRetryDelay = 20000; // 20s wait on 503
        this._allModelsBackoff = 60000;    // 60s when all models rate-limited
        this._activeRequests = 0;
        this._queue = [];
        this._cancelled = false;
        this._lastRequestTime = 0;
    }

    cancel() { this._cancelled = true; }

    async analyzeFrame(frameBlob, timestamp) {
        const base64 = await this._blobToBase64(frameBlob);
        const dataUri = `data:image/jpeg;base64,${base64}`;
        const prompt = HuggingFaceClient._createVisionPrompt();

        const body = {
            model: null, // set per-request
            messages: [{
                role: 'user',
                content: [
                    { type: 'text', text: prompt },
                    { type: 'image_url', image_url: { url: dataUri } },
                ],
            }],
            temperature: 0.1,
            max_tokens: 1024,
        };

        const { text, model } = await this._sendWithConcurrency(body);
        const parsed = HuggingFaceClient._extractJson(text);
        return FrameAnalysis.fromApiResponse(parsed, timestamp, frameBlob, model);
    }

    async analyzeFramesBatch(frames, onProgress) {
        const results = [];
        const total = frames.length;
        let completed = 0;

        const executing = new Set();

        for (let i = 0; i < frames.length; i++) {
            if (this._cancelled) throw new Error('Analysis cancelled');

            const frame = frames[i];
            const p = this.analyzeFrame(frame.blob, frame.timestamp)
                .then((result) => {
                    results[i] = result;
                    completed++;
                    if (onProgress) {
                        onProgress({
                            current: completed,
                            total,
                            percent: Math.round((completed / total) * 100),
                            timestamp: frame.timestamp,
                        });
                    }
                })
                .catch((err) => {
                    const errMsg = (err && err.message) ? err.message : String(err || 'Unknown error');
                    console.error(`Frame analysis failed at ${frame.timestamp}s:`, errMsg);
                    results[i] = new FrameAnalysis({
                        timestamp: frame.timestamp,
                        metadata: { error: errMsg },
                    });
                    completed++;
                    if (onProgress) {
                        onProgress({ current: completed, total, percent: Math.round((completed / total) * 100) });
                    }
                })
                .finally(() => executing.delete(p));

            executing.add(p);

            if (executing.size >= this._concurrency) {
                await Promise.race(executing);
            }
        }

        await Promise.all(executing);
        return results;
    }

    // --- Internal ---

    _getCurrentModel() {
        return this._models[this._currentModelIndex];
    }

    _rotateModel() {
        this._currentModelIndex = (this._currentModelIndex + 1) % this._models.length;
        return this._getCurrentModel();
    }

    async _sendWithConcurrency(body) {
        while (this._activeRequests >= this._concurrency) {
            await new Promise((r) => setTimeout(r, 200));
            if (this._cancelled) throw new Error('Cancelled');
        }

        const now = Date.now();
        const elapsed = now - this._lastRequestTime;
        if (elapsed < this._requestDelay) {
            await new Promise((r) => setTimeout(r, this._requestDelay - elapsed));
        }

        this._activeRequests++;
        this._lastRequestTime = Date.now();

        try {
            return await this._sendWithFallback(body);
        } finally {
            this._activeRequests--;
        }
    }

    async _sendWithFallback(body) {
        const totalModels = this._models.length;
        let modelsTriedInRound = 0;
        let lastError;

        for (let attempt = 0; attempt < this._maxRetries * totalModels; attempt++) {
            if (this._cancelled) throw new Error('Cancelled');

            const model = this._getCurrentModel();
            body.model = model;
            const url = `${this._baseUrl}/${model}/v1/chat/completions`;

            try {
                const resp = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${this._apiKey}`,
                    },
                    body: JSON.stringify(body),
                    signal: AbortSignal.timeout(this._coldStartTimeout),
                });

                if (resp.status === 401) {
                    throw new Error('Invalid HuggingFace API token. Please check your token in Settings.');
                }

                if (resp.status === 429) {
                    modelsTriedInRound++;
                    console.warn(`Rate limited (429) on ${model}, switching model...`);
                    this._rotateModel();

                    if (modelsTriedInRound >= totalModels) {
                        console.warn(`All models rate-limited, waiting ${this._allModelsBackoff / 1000}s...`);
                        await new Promise((r) => setTimeout(r, this._allModelsBackoff));
                        modelsTriedInRound = 0;
                    }
                    lastError = new Error(`Rate limited (429) on ${model}`);
                    continue;
                }

                if (resp.status === 503) {
                    console.warn(`Model loading (503): ${model}. Waiting ${this._coldStartRetryDelay / 1000}s...`);
                    console.log('Model warming up... This may take 10-30 seconds on first request.');
                    await new Promise((r) => setTimeout(r, this._coldStartRetryDelay));
                    lastError = new Error(`Model loading (503): ${model}`);
                    continue;
                }

                if (!resp.ok) {
                    const errBody = await resp.text();
                    throw new Error(`HuggingFace API error ${resp.status}: ${errBody}`);
                }

                const data = await resp.json();
                const choice = data.choices?.[0];
                if (!choice?.message?.content) {
                    throw new Error('Empty response from HuggingFace');
                }

                modelsTriedInRound = 0;
                return { text: choice.message.content, model };

            } catch (err) {
                if (err.name === 'TimeoutError') {
                    lastError = new Error(`Request to ${model} timed out (cold start may take longer)`);
                    console.warn(lastError.message);
                    this._rotateModel();
                    continue;
                }
                if (err.message.includes('Invalid HuggingFace API token')) {
                    throw err;
                }
                lastError = err;
                const backoff = this._initialBackoff * Math.pow(2, Math.floor(attempt / totalModels));
                console.warn(`HuggingFace attempt ${attempt + 1} failed (${model}), retrying in ${backoff}ms...`, err.message);
                await new Promise((r) => setTimeout(r, backoff));
            }
        }
        throw lastError;
    }

    _blobToBase64(blob) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => {
                const base64 = reader.result.split(',')[1];
                resolve(base64);
            };
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
    }

    static _createVisionPrompt() {
        return (
            'You are an expert FPS game footage analyst. Analyze this game screenshot ' +
            'carefully, paying attention to the HUD elements (kill feed, minimap, ' +
            'health/armor bars, ammo counter, scoreboard), player perspective, and ' +
            'on-screen action.\n\n' +
            'Provide a JSON response with these fields:\n\n' +
            '{\n' +
            '    "kill_log": boolean (true if kill feed shows a recent kill by the player),\n' +
            '    "kill_count": integer (number of kills visible in kill feed for the player, 0 if none),\n' +
            '    "match_status": string ("normal", "clutch", "victory", "defeat", "overtime"),\n' +
            '    "action_intensity": string ("very_high", "high", "medium", "low"),\n' +
            '    "enemy_visible": boolean (true if enemy players are visible on screen),\n' +
            '    "enemy_count": integer (number of visible enemy players, 0 if none),\n' +
            '    "ui_elements": string (describe visible HUD elements),\n' +
            '    "visual_quality": string ("cinematic", "high", "normal", "low"),\n' +
            '    "scene_description": string (brief description of the action),\n' +
            '    "confidence": float (0.0 to 1.0, your confidence in this analysis)\n' +
            '}\n\n' +
            'Guidelines:\n' +
            '- action_intensity: very_high = active multi-kill/clutch, high = active combat, ' +
            'medium = positioning/utility, low = idle/walking\n' +
            '- visual_quality: cinematic = dramatic angle/lighting, high = clear action shot, ' +
            'normal = standard gameplay, low = obscured/dark\n' +
            '- Be precise about kill_count: count individual kill entries in the kill feed\n' +
            '- confidence: rate how certain you are about the analysis overall\n\n' +
            'Only respond with valid JSON, no additional text.'
        );
    }

    static _extractJson(text) {
        // Try direct parse first
        try {
            return JSON.parse(text);
        } catch (_) { /* fallthrough */ }

        // Strip markdown code fences if present
        const fenceMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/);
        if (fenceMatch) {
            try { return JSON.parse(fenceMatch[1].trim()); } catch (_) { /* fallthrough */ }
        }

        // Try to find a JSON object in the text
        const match = text.match(/\{[^{}]*\}/s);
        if (match) {
            try { return JSON.parse(match[0]); } catch (_) { /* fallthrough */ }
        }

        return {
            kill_log: false,
            match_status: 'unknown',
            action_intensity: 'low',
        };
    }
}
