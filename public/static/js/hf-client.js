// ClipMontage — HuggingFace Vision Client (fallback provider)
// Extends VisionProvider from vision-client.js

class HuggingFaceVisionClient extends VisionProvider {
    // Default model list — can be overridden by passing a custom model in settings
    // Only vision-capable models confirmed available on the hf-inference serverless endpoint
    static DEFAULT_MODELS = [
        'meta-llama/Llama-3.2-11B-Vision-Instruct',
        'meta-llama/Llama-3.2-90B-Vision-Instruct',
    ];

    constructor(apiKey, hfModel) {
        super();
        if (!apiKey) throw new Error('HuggingFace API token is required');
        this._apiKey = apiKey;
        // If the user supplied a custom model, put it first
        const customModel = (hfModel || '').trim();
        this._models = customModel
            ? [customModel, ...HuggingFaceVisionClient.DEFAULT_MODELS.filter((m) => m !== customModel)]
            : [...HuggingFaceVisionClient.DEFAULT_MODELS];
        this._currentModelIndex = 0;
        this._baseUrl = 'https://router.huggingface.co/hf-inference/models';
        this._maxRetries = 3;
        this._initialBackoff = 2000;
        this._concurrency = 1;
        this._requestDelay = 2000;
        this._coldStartTimeout = 60000;
        this._coldStartRetryDelay = 15000;
        this._allModelsBackoff = 30000;
        this._activeRequests = 0;
        this._lastRequestTime = 0;
        // Shared across all frames — once a model 404s it stays dead for this session
        this._unavailableModels = new Set();
    }

    async analyzeFrame(frameBlob, timestamp) {
        const base64 = await this._blobToBase64(frameBlob);
        const dataUri = `data:image/jpeg;base64,${base64}`;
        const prompt = VisionProvider._createVisionPrompt();

        const body = {
            model: null,
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
        const parsed = VisionProvider._extractJson(text);
        return FrameAnalysis.fromApiResponse(parsed, timestamp, frameBlob, model);
    }

    // Override batch to use concurrency control
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

    async testConnection() {
        // Probe every model to find which are actually available
        const results = await Promise.all(this._models.map(async (model) => {
            const url = `${this._baseUrl}/${model}/v1/chat/completions`;
            try {
                const resp = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${this._apiKey}`,
                    },
                    body: JSON.stringify({
                        model,
                        messages: [{ role: 'user', content: 'ping' }],
                        max_tokens: 1,
                    }),
                    signal: AbortSignal.timeout(15000),
                });
                if (resp.status === 401) throw new Error('Invalid HuggingFace API token');
                if (resp.status === 404) return { model, available: false };
                // 429 / 503 / 200 = endpoint exists, auth ok
                return { model, available: true };
            } catch (err) {
                if (err.message.includes('Invalid HuggingFace API token')) throw err;
                return { model, available: false };
            }
        }));

        const available = results.filter((r) => r.available).map((r) => r.model);
        const unavailable = results.filter((r) => !r.available).map((r) => r.model);

        // Mark permanently unavailable models so frames skip them immediately
        unavailable.forEach((m) => this._unavailableModels.add(m));

        if (available.length === 0) {
            throw new Error(
                `No HuggingFace models are available on the serverless endpoint.\n` +
                `Checked: ${this._models.join(', ')}\n` +
                `All returned 404. Please specify a working Model ID in Settings, or switch to Groq / Gemini.`
            );
        }
        return { available, unavailable };
    }

    // --- Internal ---

    _getCurrentModel() { return this._models[this._currentModelIndex]; }
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

            // All models confirmed 404 (shared across frames) — fail fast
            if (this._unavailableModels.size >= totalModels) {
                throw new Error(
                    `All HuggingFace models returned 404 (not available on free serverless inference). ` +
                    `Please open Settings and either: (1) enter a working Model ID, or (2) switch to Groq or Gemini.`
                );
            }

            // Skip this model if already confirmed 404
            if (this._unavailableModels.has(model)) {
                this._rotateModel();
                continue;
            }

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
                    console.warn(`[HuggingFace] Model cold-starting: ${model}. Waiting ${this._coldStartRetryDelay / 1000}s... (this is normal for free-tier models)`);
                    await new Promise((r) => setTimeout(r, this._coldStartRetryDelay));
                    lastError = new Error(`HuggingFace model is warming up (503). Retrying...`);
                    continue;
                }
                if (resp.status === 404) {
                    console.warn(`[HuggingFace] Model not available on serverless endpoint (404): ${model}, switching model...`);
                    this._unavailableModels.add(model);
                    this._rotateModel();
                    lastError = new Error(`HuggingFace API error 404: Not Found`);
                    continue;
                }
                if (!resp.ok) {
                    const errBody = await resp.text();
                    throw new Error(`HuggingFace API error ${resp.status}: ${errBody}`);
                }

                const data = await resp.json();
                const choice = data.choices?.[0];
                if (!choice?.message?.content) throw new Error('Empty response from HuggingFace');

                modelsTriedInRound = 0;
                return { text: choice.message.content, model };

            } catch (err) {
                if (err.name === 'TimeoutError') {
                    lastError = new Error(`Request to ${model} timed out`);
                    console.warn(lastError.message);
                    this._rotateModel();
                    continue;
                }
                if (err.message.includes('Invalid HuggingFace API token')) throw err;
                lastError = err;
                const backoff = this._initialBackoff * Math.pow(2, Math.floor(attempt / totalModels));
                console.warn(`HuggingFace attempt ${attempt + 1} failed (${model}), retrying in ${backoff}ms...`, err.message);
                await new Promise((r) => setTimeout(r, backoff));
            }
        }
        throw lastError;
    }
}

// Backward-compatibility alias (test_release.mjs checks typeof HuggingFaceClient)
// eslint-disable-next-line no-unused-vars
const HuggingFaceClient = HuggingFaceVisionClient;
