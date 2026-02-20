---
title: ClipMontage Ollama API
emoji: 🎬
colorFrom: purple
colorTo: blue
sdk: docker
app_port: 7860
---

# ClipMontage Ollama Vision API

Ollama Vision model server for [ClipMontage](https://moviecutter.web.app/) video analysis.

## API Usage

```bash
curl https://<your-space>.hf.space/api/chat -d '{
  "model": "llama3.2-vision",
  "stream": false,
  "messages": [{"role": "user", "content": "Hello"}]
}'
```
