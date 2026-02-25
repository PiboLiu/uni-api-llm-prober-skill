# Uni-API LLM Endpoints (from https://uni-api.cstcloud.cn/doc/llm/)

基础地址：

- `https://uni-api.cstcloud.cn/v1`

鉴权：

- Header `Authorization: Bearer <API_KEY>`

## Standard

- Models: `GET /models`
- Chat: `POST /chat/completions`
- Embeddings: `POST /embeddings`
- Rerank: `POST /rerank`

## Special

- Web Search: `POST /chat/web_search`
- AI Search: `POST /chat/ai_search`
- DeepSeek OCR: `POST /chat/deepseek_ocr`

## Request format notes

- Chat-like endpoints generally use:
  - `model`
  - `messages` (role/content)
- Embeddings use:
  - `model`
  - `input`
- Rerank use:
  - `model`
  - `query`
  - `documents`
