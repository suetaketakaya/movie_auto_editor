// ClipMontage — Vision Provider Abstraction
// Supports: Groq (fast/free), Gemini 1.5 Flash (accurate/free), Ollama (local), HuggingFace (fallback)

// ══════════════════════════════════════════════════════════
// BASE CLASS
// ══════════════════════════════════════════════════════════

class VisionProvider {
    constructor() {
        this._cancelled = false;
    }

    cancel() { this._cancelled = true; }

    /** @returns {Promise<FrameAnalysis>} */
    async analyzeFrame(frameBlob, timestamp) {
        throw new Error('analyzeFrame() must be implemented by subclass');
    }

    async analyzeFramesBatch(frames, onProgress) {
        const results = [];
        const total = frames.length;
        let completed = 0;

        for (let i = 0; i < frames.length; i++) {
            if (this._cancelled) throw new Error('Analysis cancelled');

            const frame = frames[i];
            try {
                results[i] = await this.analyzeFrame(frame.blob, frame.timestamp);
            } catch (err) {
                const errMsg = (err && err.message) ? err.message : String(err || 'Unknown error');
                console.error(`Frame analysis failed at ${frame.timestamp}s:`, errMsg);
                results[i] = new FrameAnalysis({
                    timestamp: frame.timestamp,
                    metadata: { error: errMsg },
                });
            }
            completed++;
            if (onProgress) {
                onProgress({
                    current: completed,
                    total,
                    percent: Math.round((completed / total) * 100),
                    timestamp: frame.timestamp,
                });
            }
        }
        return results;
    }

    // Shared utilities

    _blobToBase64(blob) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result.split(',')[1]);
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
        try { return JSON.parse(text); } catch (_) { /* fallthrough */ }
        const fenceMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/);
        if (fenceMatch) {
            try { return JSON.parse(fenceMatch[1].trim()); } catch (_) { /* fallthrough */ }
        }
        const match = text.match(/\{[^{}]*\}/s);
        if (match) {
            try { return JSON.parse(match[0]); } catch (_) { /* fallthrough */ }
        }
        console.warn('[VisionAI] Could not parse response as JSON, using fallback defaults. Response was:', text?.slice(0, 200));
        return { kill_log: false, match_status: 'unknown', action_intensity: 'low' };
    }
}

// ══════════════════════════════════════════════════════════
// GROQ VISION CLIENT
// Fast, free (7,000 req/day), OpenAI-compatible API
// ══════════════════════════════════════════════════════════

class GroqVisionClient extends VisionProvider {
    constructor(apiKey) {
        super();
        if (!apiKey) throw new Error('Groq API key is required');
        this._apiKey = apiKey;
        this._baseUrl = 'https://api.groq.com/openai/v1/chat/completions';
        // llama-3.2-11b-vision-preview: Groq free tier vision model (confirmed available)
        // llama-3.2-90b-vision-preview: higher quality, may require paid tier
        this._model = 'llama-3.2-11b-vision-preview';
        this._requestDelay = 500;
        this._lastRequestTime = 0;
    }

    async analyzeFrame(frameBlob, timestamp) {
        if (this._cancelled) throw new Error('Cancelled');

        const now = Date.now();
        const elapsed = now - this._lastRequestTime;
        if (elapsed < this._requestDelay) {
            await new Promise((r) => setTimeout(r, this._requestDelay - elapsed));
        }
        this._lastRequestTime = Date.now();

        const base64 = await this._blobToBase64(frameBlob);
        const dataUri = `data:image/jpeg;base64,${base64}`;
        const prompt = VisionProvider._createVisionPrompt();

        const body = {
            model: this._model,
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

        const resp = await fetch(this._baseUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this._apiKey}`,
            },
            body: JSON.stringify(body),
            signal: AbortSignal.timeout(30000),
        });

        if (resp.status === 401) throw new Error('Invalid Groq API key. Please check your key in Settings.');
        if (resp.status === 429) throw new Error('RATE_LIMIT');
        if (!resp.ok) {
            const errBody = await resp.text();
            throw new Error(`Groq API error ${resp.status}: ${errBody}`);
        }

        const data = await resp.json();
        const text = data.choices?.[0]?.message?.content;
        if (!text) throw new Error('Empty response from Groq');

        const parsed = VisionProvider._extractJson(text);
        return FrameAnalysis.fromApiResponse(parsed, timestamp, frameBlob, `groq/${this._model}`);
    }

    async testConnection() {
        const resp = await fetch('https://api.groq.com/openai/v1/models', {
            headers: { 'Authorization': `Bearer ${this._apiKey}` },
            signal: AbortSignal.timeout(10000),
        });
        if (resp.status === 401) throw new Error('Invalid Groq API key');
        if (!resp.ok) throw new Error(`Groq connection failed: ${resp.status}`);
        return true;
    }
}

// ══════════════════════════════════════════════════════════
// GEMINI VISION CLIENT
// High accuracy, free (1,500 req/day), native multimodal
// ══════════════════════════════════════════════════════════

class GeminiVisionClient extends VisionProvider {
    constructor(apiKey) {
        super();
        if (!apiKey) throw new Error('Gemini API key is required');
        this._apiKey = apiKey;
        this._model = 'gemini-1.5-flash';
        this._baseUrl = `https://generativelanguage.googleapis.com/v1beta/models/${this._model}:generateContent`;
        this._requestDelay = 1000;
        this._lastRequestTime = 0;
    }

    async analyzeFrame(frameBlob, timestamp) {
        if (this._cancelled) throw new Error('Cancelled');

        const now = Date.now();
        const elapsed = now - this._lastRequestTime;
        if (elapsed < this._requestDelay) {
            await new Promise((r) => setTimeout(r, this._requestDelay - elapsed));
        }
        this._lastRequestTime = Date.now();

        const base64 = await this._blobToBase64(frameBlob);
        const prompt = VisionProvider._createVisionPrompt();

        const body = {
            contents: [{
                parts: [
                    { text: prompt },
                    { inline_data: { mime_type: 'image/jpeg', data: base64 } },
                ],
            }],
            generationConfig: {
                temperature: 0.1,
                maxOutputTokens: 1024,
            },
        };

        const url = `${this._baseUrl}?key=${this._apiKey}`;
        const resp = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
            signal: AbortSignal.timeout(30000),
        });

        if (resp.status === 400) {
            const errBody = await resp.text();
            if (errBody.includes('API_KEY_INVALID')) throw new Error('Invalid Gemini API key. Please check your key in Settings.');
            throw new Error(`Gemini API error 400: ${errBody}`);
        }
        if (resp.status === 429) throw new Error('RATE_LIMIT');
        if (!resp.ok) {
            const errBody = await resp.text();
            throw new Error(`Gemini API error ${resp.status}: ${errBody}`);
        }

        const data = await resp.json();
        const text = data.candidates?.[0]?.content?.parts?.[0]?.text;
        if (!text) throw new Error('Empty response from Gemini');

        const parsed = VisionProvider._extractJson(text);
        return FrameAnalysis.fromApiResponse(parsed, timestamp, frameBlob, `gemini/${this._model}`);
    }

    async testConnection() {
        const url = `https://generativelanguage.googleapis.com/v1beta/models?key=${this._apiKey}`;
        const resp = await fetch(url, { signal: AbortSignal.timeout(10000) });
        if (resp.status === 400 || resp.status === 401 || resp.status === 403) {
            throw new Error('Invalid Gemini API key');
        }
        if (!resp.ok) throw new Error(`Gemini connection failed: ${resp.status}`);
        return true;
    }
}

// ══════════════════════════════════════════════════════════
// OLLAMA VISION CLIENT
// Local, unlimited, requires Ollama running with OLLAMA_ORIGINS=*
// ══════════════════════════════════════════════════════════

class OllamaVisionClient extends VisionProvider {
    constructor(baseUrl) {
        super();
        this._baseUrl = (baseUrl || 'http://localhost:11434').replace(/\/$/, '');
        this._model = 'llama3.2-vision:latest';
        this._requestDelay = 0;
        this._lastRequestTime = 0;
    }

    async analyzeFrame(frameBlob, timestamp) {
        if (this._cancelled) throw new Error('Cancelled');

        const base64 = await this._blobToBase64(frameBlob);
        const prompt = VisionProvider._createVisionPrompt();

        const body = {
            model: this._model,
            messages: [{
                role: 'user',
                content: prompt,
                images: [base64],
            }],
            stream: false,
            options: { temperature: 0.1 },
        };

        let resp;
        try {
            resp = await fetch(`${this._baseUrl}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
                signal: AbortSignal.timeout(120000),
            });
        } catch (err) {
            throw new Error(`Ollama not reachable at ${this._baseUrl}. Ensure Ollama is running with OLLAMA_ORIGINS=* env.`);
        }

        if (!resp.ok) {
            const errBody = await resp.text();
            throw new Error(`Ollama error ${resp.status}: ${errBody}`);
        }

        const data = await resp.json();
        const text = data.message?.content;
        if (!text) throw new Error('Empty response from Ollama');

        const parsed = VisionProvider._extractJson(text);
        return FrameAnalysis.fromApiResponse(parsed, timestamp, frameBlob, `ollama/${this._model}`);
    }

    async testConnection() {
        let resp;
        try {
            resp = await fetch(`${this._baseUrl}/api/tags`, { signal: AbortSignal.timeout(5000) });
        } catch (_) {
            throw new Error(`Ollama not reachable at ${this._baseUrl}`);
        }
        if (!resp.ok) throw new Error(`Ollama connection failed: ${resp.status}`);
        const data = await resp.json();
        const models = (data.models || []).map((m) => m.name);
        const hasVision = models.some((m) => m.includes('llama3.2-vision') || m.includes('llava'));
        if (!hasVision) {
            throw new Error(`No vision model found in Ollama. Pull one with: ollama pull llama3.2-vision`);
        }
        return true;
    }
}

// ══════════════════════════════════════════════════════════
// PROVIDER FACTORY WITH AUTO-FALLBACK
// ══════════════════════════════════════════════════════════

class VisionProviderFactory {
    /**
     * Create a single provider from settings.
     * @param {{ provider: string, apiKey: string, ollamaUrl?: string }} settings
     */
    static create(settings) {
        const { provider, apiKey, ollamaUrl, hfModel } = settings;
        switch (provider) {
            case 'groq': return new GroqVisionClient(apiKey);
            case 'gemini': return new GeminiVisionClient(apiKey);
            case 'ollama': return new OllamaVisionClient(ollamaUrl);
            case 'huggingface': return new HuggingFaceVisionClient(apiKey, hfModel);
            default: throw new Error(`Unknown provider: ${provider}`);
        }
    }

    /**
     * Create a FallbackVisionClient that chains multiple providers.
     * @param {Array<{provider: string, apiKey?: string, ollamaUrl?: string}>} providerConfigs
     */
    static createWithFallback(providerConfigs) {
        const clients = providerConfigs
            .filter((c) => {
                if (c.provider === 'ollama') return true;
                return !!c.apiKey;
            })
            .map((c) => VisionProviderFactory.create(c));

        if (clients.length === 0) {
            throw new Error('No valid vision providers configured. Please set an API key in Settings.');
        }
        if (clients.length === 1) return clients[0];
        return new FallbackVisionClient(clients);
    }

    /** Load provider settings from sessionStorage */
    static loadSettings() {
        const provider = sessionStorage.getItem('vision_provider') || 'huggingface';
        // Per-provider key takes priority; fall back to legacy shared key
        const apiKey = sessionStorage.getItem(`vision_api_key_${provider}`)
            || sessionStorage.getItem('vision_api_key')
            || sessionStorage.getItem('hf_api_key')
            || '';
        return {
            provider,
            apiKey,
            ollamaUrl: sessionStorage.getItem('ollama_url') || 'http://localhost:11434',
            hfModel: sessionStorage.getItem('hf_model') || '',
        };
    }

    /** Save provider settings to sessionStorage */
    static saveSettings({ provider, apiKey, ollamaUrl, hfModel }) {
        sessionStorage.setItem('vision_provider', provider);
        // Save per-provider key so switching providers doesn't lose the previous key
        if (apiKey) sessionStorage.setItem(`vision_api_key_${provider}`, apiKey);
        // Also update generic key (used by legacy paths)
        sessionStorage.setItem('vision_api_key', apiKey || '');
        if (ollamaUrl) sessionStorage.setItem('ollama_url', ollamaUrl);
        if (hfModel !== undefined) sessionStorage.setItem('hf_model', hfModel);
        // Legacy compat
        if (provider === 'huggingface' && apiKey) sessionStorage.setItem('hf_api_key', apiKey);
    }

    /** Load only the saved key for a given provider (used by Settings UI on provider switch) */
    static getKeyForProvider(provider) {
        return sessionStorage.getItem(`vision_api_key_${provider}`)
            || (provider === 'huggingface' ? sessionStorage.getItem('hf_api_key') : '')
            || '';
    }
}

// ══════════════════════════════════════════════════════════
// FALLBACK VISION CLIENT
// Tries providers in order, falls through on rate limits
// ══════════════════════════════════════════════════════════

class FallbackVisionClient extends VisionProvider {
    constructor(clients) {
        super();
        this._clients = clients;
        this._currentIndex = 0;
    }

    cancel() {
        super.cancel();
        this._clients.forEach((c) => c.cancel());
    }

    async analyzeFrame(frameBlob, timestamp) {
        const totalClients = this._clients.length;
        let lastError;

        for (let i = 0; i < totalClients; i++) {
            const idx = (this._currentIndex + i) % totalClients;
            const client = this._clients[idx];

            try {
                const result = await client.analyzeFrame(frameBlob, timestamp);
                this._currentIndex = idx; // stick to working provider
                return result;
            } catch (err) {
                const msg = (err && err.message) ? err.message : String(err);
                if (msg === 'RATE_LIMIT' || msg.includes('429') || msg.includes('rate limit')) {
                    console.warn(`Provider ${idx} rate limited, falling back...`);
                    lastError = err;
                    continue;
                }
                // Non-rate-limit errors propagate immediately
                throw err;
            }
        }
        throw lastError || new Error('All vision providers failed or rate limited');
    }
}
