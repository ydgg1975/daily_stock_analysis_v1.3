# LLM 설정 가이드

Daily Stock Analysis는 LiteLLM을 통해 여러 LLM provider를 공통 방식으로 호출합니다. 이 문서는 로컬 실행, Docker, GitHub Actions, WebUI, 데스크톱 앱에서 LLM을 설정하는 방법을 설명합니다.

## 설정 방식과 우선순위

LLM 설정은 세 가지 방식이 있습니다.

| 방식 | 용도 | 우선순위 |
| --- | --- | --- |
| `LITELLM_CONFIG` YAML | 고급 라우팅, 여러 deployment, RPM/TPM 제어 | 1 |
| `LLM_CHANNELS` 채널 모드 | 여러 provider와 fallback 구성 | 2 |
| Legacy provider keys | 빠른 시작, 단일 provider | 3 |

우선순위:

```text
LITELLM_CONFIG > LLM_CHANNELS > legacy provider keys
```

`LLM_CHANNELS`를 켰다면 `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY` 같은 legacy key가 이번 요청에서 사용되지 않을 수 있습니다. 혼동을 줄이려면 한 가지 방식을 선택해 정리하세요.

현재 런타임 의존성은 `requirements.txt`의 LiteLLM 버전 제약을 따릅니다.

```text
litellm>=1.80.10,!=1.82.7,!=1.82.8,<2.0.0
```

## 빠른 시작

가장 단순한 방법은 API Key 하나와 사용할 모델을 지정하는 것입니다.

### OpenAI 또는 OpenAI 호환 API

```env
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
LITELLM_MODEL=openai/gpt-5.5
```

OpenAI 호환 gateway를 사용할 때도 모델명에는 보통 `openai/` 접두사를 붙입니다.

```env
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://your-gateway.example.com/v1
LITELLM_MODEL=openai/gpt-5.5
```

### Gemini

```env
GEMINI_API_KEY=xxx
LITELLM_MODEL=gemini/gemini-3.1-pro-preview
```

### Anthropic

```env
ANTHROPIC_API_KEY=sk-ant-xxx
LITELLM_MODEL=anthropic/claude-sonnet-4-6
```

### DeepSeek

```env
DEEPSEEK_API_KEY=sk-xxx
LITELLM_MODEL=deepseek/deepseek-v4-flash
```

### Ollama

Ollama는 API Key가 필요하지 않습니다.

```env
OLLAMA_API_BASE=http://localhost:11434
LITELLM_MODEL=ollama/qwen3:8b
```

주의: Ollama에는 `OPENAI_BASE_URL` 대신 `OLLAMA_API_BASE`를 사용하세요. 잘못 설정하면 `/api/generate/api/show` 같은 잘못된 URL로 호출되어 404가 날 수 있습니다.

## 채널 모드

여러 provider, 여러 Key, fallback을 쓰려면 채널 모드를 사용합니다.

기본 규칙:

```env
LLM_CHANNELS=channel1,channel2
LLM_<CHANNEL>_PROTOCOL=openai
LLM_<CHANNEL>_BASE_URL=https://example.com/v1
LLM_<CHANNEL>_API_KEY=sk-xxx
LLM_<CHANNEL>_MODELS=model1,model2
```

채널 이름은 대문자로 변환되어 환경 변수 이름에 들어갑니다. 예를 들어 `my_proxy` 채널은 `LLM_MY_PROXY_*` 키를 사용합니다.

### OpenAI + Gemini fallback

```env
LLM_CHANNELS=openai,gemini

LLM_OPENAI_PROTOCOL=openai
LLM_OPENAI_BASE_URL=https://api.openai.com/v1
LLM_OPENAI_API_KEY=sk-xxx
LLM_OPENAI_MODELS=gpt-5.5,gpt-5.4-mini

LLM_GEMINI_PROTOCOL=gemini
LLM_GEMINI_API_KEY=xxx
LLM_GEMINI_MODELS=gemini-3.1-pro-preview

LITELLM_MODEL=openai/gpt-5.5
LITELLM_FALLBACK_MODELS=gemini/gemini-3.1-pro-preview
```

### DeepSeek + proxy

```env
LLM_CHANNELS=deepseek,my_proxy

LLM_DEEPSEEK_PROTOCOL=deepseek
LLM_DEEPSEEK_API_KEY=sk-xxx
LLM_DEEPSEEK_BASE_URL=https://api.deepseek.com
LLM_DEEPSEEK_MODELS=deepseek-v4-flash,deepseek-v4-pro

LLM_MY_PROXY_PROTOCOL=openai
LLM_MY_PROXY_BASE_URL=https://your-proxy.example.com/v1
LLM_MY_PROXY_API_KEY=sk-xxx
LLM_MY_PROXY_MODELS=gpt-5.5,claude-sonnet-4-6

LITELLM_MODEL=deepseek/deepseek-v4-flash
AGENT_LITELLM_MODEL=deepseek/deepseek-v4-pro
LITELLM_FALLBACK_MODELS=openai/gpt-5.5
```

### Ollama 채널

```env
LLM_CHANNELS=ollama
LLM_OLLAMA_PROTOCOL=ollama
LLM_OLLAMA_BASE_URL=http://localhost:11434
LLM_OLLAMA_MODELS=qwen3:8b,llama3.2

LITELLM_MODEL=ollama/qwen3:8b
```

### Gemini 단독 채널

```env
LLM_CHANNELS=gemini
LLM_GEMINI_PROTOCOL=gemini
LLM_GEMINI_API_KEY=xxx
LLM_GEMINI_MODELS=gemini-3.1-pro-preview

LITELLM_MODEL=gemini/gemini-3.1-pro-preview
```

## 주요 provider 예시

### Anspire Open

```env
LLM_CHANNELS=anspire
LLM_ANSPIRE_PROTOCOL=openai
LLM_ANSPIRE_BASE_URL=https://open-gateway.anspire.cn/v6
LLM_ANSPIRE_API_KEY=sk-xxx
LLM_ANSPIRE_MODELS=Doubao-Seed-2.0-lite,Doubao-Seed-2.0-pro

LITELLM_MODEL=openai/Doubao-Seed-2.0-lite
```

### AIHubMix

```env
LLM_CHANNELS=aihubmix
LLM_AIHUBMIX_PROTOCOL=openai
LLM_AIHUBMIX_BASE_URL=https://aihubmix.com/v1
LLM_AIHUBMIX_API_KEY=sk-xxx
LLM_AIHUBMIX_MODELS=gpt-5.5,claude-sonnet-4-6,gemini-3.1-pro-preview

LITELLM_MODEL=openai/gpt-5.5
```

### OpenRouter

```env
LLM_CHANNELS=openrouter
LLM_OPENROUTER_PROTOCOL=openai
LLM_OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
LLM_OPENROUTER_API_KEY=sk-or-xxx
LLM_OPENROUTER_MODELS=~anthropic/claude-sonnet-latest,~openai/gpt-latest

LITELLM_MODEL=openai/~anthropic/claude-sonnet-latest
```

### Moonshot / Kimi

```env
LLM_CHANNELS=moonshot
LLM_MOONSHOT_PROTOCOL=openai
LLM_MOONSHOT_BASE_URL=https://api.moonshot.cn/v1
LLM_MOONSHOT_API_KEY=sk-xxx
LLM_MOONSHOT_MODELS=kimi-k2.6,kimi-k2.5

LITELLM_MODEL=openai/kimi-k2.6
```

### DashScope

```env
LLM_CHANNELS=dashscope
LLM_DASHSCOPE_PROTOCOL=openai
LLM_DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_DASHSCOPE_API_KEY=sk-xxx
LLM_DASHSCOPE_MODELS=qwen3.6-plus,qwen3.6-flash

LITELLM_MODEL=openai/qwen3.6-plus
```

### MiniMax

```env
LLM_CHANNELS=minimax
LLM_MINIMAX_PROTOCOL=openai
LLM_MINIMAX_BASE_URL=https://api.minimax.io/v1
LLM_MINIMAX_API_KEY=xxx
LLM_MINIMAX_MODELS=MiniMax-M2.7,MiniMax-M2.7-highspeed

LITELLM_MODEL=openai/MiniMax-M2.7
```

MiniMax를 OpenAI 호환 채널로 연결하면서 모델명 자체에 provider 접두사가 필요하다면 `minimax/<model>` 형식을 그대로 입력합니다. Web 설정 화면은 이 값을 임의로 `openai/minimax/<model>`처럼 바꾸지 않아야 합니다.

## Agent 모델

AI 종목 상담 Agent는 일반 분석과 같은 설정 우선순위를 따릅니다.

```text
LITELLM_CONFIG > LLM_CHANNELS > legacy provider keys
```

`AGENT_LITELLM_MODEL`을 비워두면 Agent는 `LITELLM_MODEL`을 상속합니다.

```env
AGENT_LITELLM_MODEL=deepseek/deepseek-v4-pro
```

Agent는 도구 호출, JSON 구조화, 뉴스 검색을 함께 사용하므로 일반 요약 모델보다 추론과 도구 호출 안정성이 좋은 모델을 권장합니다.

## Vision 모델

이미지에서 종목 코드나 정보를 추출하는 기능은 Vision 모델을 사용합니다.

```env
VISION_MODEL=openai/gpt-5.5
VISION_PROVIDER_PRIORITY=gemini,anthropic,openai
```

`VISION_PROVIDER_PRIORITY`는 주 모델 호출 실패 시 시도할 provider 순서를 지정합니다.

## YAML 고급 설정

LiteLLM YAML은 가장 높은 우선순위를 가지며, 설정하면 채널 모드와 legacy provider key보다 먼저 사용됩니다.

`.env`:

```env
LITELLM_CONFIG=./litellm_config.yaml
LITELLM_MODEL=my-smart-model
```

`litellm_config.yaml` 예시:

```yaml
model_list:
  - model_name: my-smart-model
    litellm_params:
      model: deepseek/deepseek-v4-flash
      api_base: https://api.deepseek.com
      api_key: "os.environ/MY_CUSTOM_SECRET_KEY"

  - model_name: ollama/qwen3:8b
    litellm_params:
      model: ollama/qwen3:8b
      api_base: http://localhost:11434
```

예시 파일은 [LiteLLM YAML 예시](examples/litellm_config.example.yaml)를 참고하세요.

## GitHub Actions

GitHub Actions에서는 민감한 값은 Secrets에, 비민감 값은 Variables에 넣습니다.

권장:

- Secrets: API Key, Token, Webhook URL, `LLM_<NAME>_API_KEY`
- Variables: 모델명, 채널명, Base URL, 실행 옵션

주의: 현재 workflow가 명시적으로 전달하지 않는 사용자 정의 채널 변수는 실행 환경에 들어가지 않을 수 있습니다. 예를 들어 `LLM_CHANNELS=my_proxy`를 쓰려면 workflow `env:`에 `LLM_MY_PROXY_*` 매핑도 필요할 수 있습니다.

## Docker 환경

Docker Compose의 `environment:` 또는 `docker run -e`로 전달한 값은 컨테이너 안에서 `.env`보다 우선할 수 있습니다. Web 설정 페이지에서 `.env`를 바꿔도 Compose 환경 변수가 계속 덮어쓰면 변경이 반영되지 않습니다.

해결:

1. Compose `environment:` 값을 함께 수정합니다.
2. 컨테이너를 재생성합니다.

```bash
docker-compose -f ./docker/docker-compose.yml down
docker-compose -f ./docker/docker-compose.yml up -d --force-recreate
```

## Temperature 호환성

일부 모델은 `temperature` 값을 제한합니다.

- Kimi K2.6 계열은 thinking 모드와 non-thinking 모드에서 허용 값이 다를 수 있습니다.
- GPT-5 / o 계열 일부 모델은 기본 temperature만 허용할 수 있습니다.
- 런타임은 현재 요청에서만 필요한 보정을 수행하며 `.env`의 `LLM_TEMPERATURE`를 조용히 고쳐 쓰지 않습니다.

```env
LLM_TEMPERATURE=0.7
```

strict temperature 모델에서 오류가 발생하면 런타임이 해당 요청을 보정해 재시도할 수 있습니다. 이 보정은 프로세스 메모리 캐시 수준이며 설정 파일에는 기록하지 않습니다.

## 설정 검사

로컬 설정 문법 검사:

```bash
python scripts/check_env.py --config
```

실제 LLM 호출 검사:

```bash
python scripts/check_env.py --llm
```

Web 설정 페이지에서는 LLM 채널 테스트 기능으로 인증, 모델 접근성, JSON, tools, stream, vision 같은 capability를 점검할 수 있습니다.

## 자주 발생하는 문제

| 증상 | 원인 | 해결 |
| --- | --- | --- |
| 주 모델 미설정 | `LITELLM_MODEL`이 비어 있음 | `provider/model` 형식으로 설정합니다. |
| 여러 Key 중 하나만 사용됨 | legacy key와 채널 모드가 섞임 | `LLM_CHANNELS` 방식으로 통일하거나 legacy만 남깁니다. |
| 400/401 오류 | API Key, Base URL, 모델명 오류 | Key 공백, `/v1`, 모델 접두사를 확인합니다. |
| 모델 접근 거부 | 계정 권한 또는 모델 미개통 | provider 콘솔에서 모델 권한을 확인합니다. |
| Timeout / ConnectionRefused | 네트워크, 프록시, provider 장애 | 접근 가능한 provider 또는 프록시를 사용합니다. |
| Ollama 404 | `OPENAI_BASE_URL`로 Ollama를 설정함 | `OLLAMA_API_BASE` 또는 Ollama 채널을 사용합니다. |
| temperature 오류 | 모델이 특정 temperature만 허용 | strict temperature 보정 로직을 사용하거나 모델별 권장값을 맞춥니다. |

## 검증 범위

LLM 설정 변경과 관련된 주요 테스트:

```bash
python -m pytest tests/test_llm_channel_config.py
python -m pytest tests/test_system_config_service.py
python -m pytest tests/test_system_config_api.py
python -m pytest tests/test_market_analyzer_generate_text.py
python -m pytest tests/test_agent_pipeline.py

cd apps/dsa-web
npm run test -- src/components/settings/__tests__/LLMChannelEditor.test.tsx
```

전체 변경 전후로는 다음도 함께 실행하는 것을 권장합니다.

```bash
python scripts/check_language_artifacts.py
git diff --check
```

## 참고 링크

- [LiteLLM](https://docs.litellm.ai/)
- [LiteLLM OpenAI Compatible](https://docs.litellm.ai/docs/providers/openai_compatible)
- [OpenAI Chat Completions](https://platform.openai.com/docs/api-reference/chat)
- [DeepSeek API](https://api-docs.deepseek.com/)
- [Anthropic Messages API](https://docs.anthropic.com/en/api/messages)
- [Gemini API](https://ai.google.dev/gemini-api/docs)
- [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [Moonshot / Kimi](https://platform.moonshot.ai/docs/guide/compatibility)

마지막 정리일: 2026-05-21
