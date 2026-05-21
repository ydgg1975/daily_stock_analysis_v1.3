# LLM provider 운영 가이드

이 문서는 프로젝트에서 사용할 수 있는 LLM provider의 설정 방식, provider별 기본값, 운영 중 자주 보는 오류를 정리합니다. 전체 설정 우선순위와 예시는 `docs/LLM_CONFIG_GUIDE.md`를 우선 참고하세요.

## 설정 방식

프로젝트는 세 가지 설정 방식을 지원합니다.

| 방식 | 용도 | 주요 설정 |
| --- | --- | --- |
| Legacy | 단일 provider 또는 기존 환경과의 호환 | `LITELLM_MODEL`, provider별 API 키 |
| Channels | 여러 provider fallback, Web UI 설정, 운영 환경 전환 | `LLM_CHANNELS`, `LLM_<CHANNEL>_*` |
| YAML | LiteLLM 고급 라우팅, 복잡한 model list 관리 | `LITELLM_CONFIG`, `LITELLM_CONFIG_YAML` |

우선순위는 `LITELLM_CONFIG` 또는 `LITELLM_CONFIG_YAML`이 가장 높고, 그 다음이 `LLM_CHANNELS`, 마지막이 legacy provider 키입니다.

## Web UI 설정 흐름

Web UI의 설정 화면에서는 다음 순서로 확인합니다.

1. 사용할 provider 채널을 추가합니다.
2. protocol, Base URL, API 키, 모델 목록을 입력합니다.
3. 기본 분석 모델과 Agent 모델을 선택합니다.
4. 연결 테스트를 실행합니다.
5. 설정을 저장한 뒤 간단한 종목 분석으로 실제 응답을 확인합니다.

연결 테스트는 API 키 유효성, endpoint 응답, 모델 접근 권한을 빠르게 확인하는 용도입니다. provider가 `/models` endpoint를 제공하지 않거나 일부 기능을 막는 경우, 연결 테스트가 제한적으로만 성공할 수 있습니다.

## Channel 예시

### OpenAI 호환 proxy

```env
LLM_CHANNELS=my_proxy
LLM_MY_PROXY_PROTOCOL=openai
LLM_MY_PROXY_BASE_URL=https://your-proxy.example.com/v1
LLM_MY_PROXY_API_KEY=sk-xxx
LLM_MY_PROXY_MODELS=gpt-5.5,claude-sonnet-4-6
LITELLM_MODEL=openai/gpt-5.5
```

### DeepSeek

```env
LLM_CHANNELS=deepseek
LLM_DEEPSEEK_PROTOCOL=deepseek
LLM_DEEPSEEK_BASE_URL=https://api.deepseek.com
LLM_DEEPSEEK_API_KEY=sk-xxx
LLM_DEEPSEEK_MODELS=deepseek-chat,deepseek-reasoner
LITELLM_MODEL=deepseek/deepseek-chat
```

### Ollama

```env
LLM_CHANNELS=ollama
LLM_OLLAMA_PROTOCOL=ollama
LLM_OLLAMA_BASE_URL=http://127.0.0.1:11434
LLM_OLLAMA_MODELS=llama3.2,qwen2.5
LITELLM_MODEL=ollama/llama3.2
```

## Provider 템플릿

| Provider | Channel 예시 | Protocol | Base URL | 모델 예시 |
| --- | --- | --- | --- | --- |
| OpenAI | `openai` | `openai` | `https://api.openai.com/v1` | `gpt-5.5`, `gpt-5.4-mini` |
| Anthropic Claude | `anthropic` | `anthropic` | provider 기본값 | `claude-sonnet-4-6`, `claude-opus-4-7` |
| Gemini | `gemini` | `gemini` | provider 기본값 | `gemini-3.1-pro-preview`, `gemini-3-flash-preview` |
| DeepSeek | `deepseek` | `deepseek` | `https://api.deepseek.com` | `deepseek-chat`, `deepseek-reasoner` |
| AIHubMix | `aihubmix` | `openai` | `https://aihubmix.com/v1` | `gpt-5.5`, `claude-sonnet-4-6` |
| Anspire Open | `anspire` | `openai` | `https://open-gateway.anspire.cn/v6` | `Doubao-Seed-2.0-lite`, `qwen3.5-flash` |
| OpenRouter | `openrouter` | `openai` | `https://openrouter.ai/api/v1` | `anthropic/claude-sonnet-latest`, `openai/gpt-latest` |
| Moonshot Kimi | `moonshot` | `openai` | `https://api.moonshot.cn/v1` | `kimi-k2.6`, `kimi-k2.5` |
| DashScope | `dashscope` | `openai` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen3.6-plus`, `qwen3.6-flash` |
| Zhipu GLM | `zhipu` | `openai` | `https://open.bigmodel.cn/api/paas/v4` | `glm-5.1`, `glm-4.7-flash` |
| MiniMax | `minimax` | `openai` | `https://api.minimax.io/v1` | `MiniMax-M2.7`, `MiniMax-M2.7-highspeed` |
| Volcengine | `volcengine` | `openai` | `https://ark.cn-beijing.volces.com/api/v3` | `doubao-seed-1-6-251015` |
| SiliconFlow | `siliconflow` | `openai` | `https://api.siliconflow.cn/v1` | `Qwen/Qwen3-235B-A22B-Thinking-2507` |
| Ollama | `ollama` | `ollama` | `http://127.0.0.1:11434` | `llama3.2`, `qwen2.5` |

OpenAI 호환 provider는 대체로 `protocol=openai`를 사용합니다. LiteLLM 모델명에는 provider prefix가 필요할 수 있으므로 `openai/<model>` 형식과 provider 문서를 함께 확인합니다.

## GitHub Actions 설정

자동 분석 워크플로에서는 Repository Variables와 Secrets를 함께 사용합니다.

| 설정 | 권장 저장 위치 | 설명 |
| --- | --- | --- |
| `LLM_CHANNELS` | Variables 또는 Secrets | 사용할 channel 목록 |
| `LLM_<CHANNEL>_PROTOCOL` | Variables | `openai`, `deepseek`, `gemini`, `anthropic`, `ollama` 등 |
| `LLM_<CHANNEL>_BASE_URL` | Variables | 공개 endpoint 주소 |
| `LLM_<CHANNEL>_MODELS` | Variables | 쉼표로 구분한 모델 목록 |
| `LLM_<CHANNEL>_ENABLED` | Variables | 비활성화하려면 `false` |
| `LLM_<CHANNEL>_API_KEY` | Secrets | 단일 API 키 |
| `LLM_<CHANNEL>_API_KEYS` | Secrets | 여러 API 키를 쉼표로 구분 |
| `LLM_<CHANNEL>_EXTRA_HEADERS` | Secrets | 별도 인증 헤더 JSON |
| `LITELLM_CONFIG_YAML` | Secrets | API 키가 포함될 수 있는 YAML 설정 |

API 키와 인증 헤더는 Variables에 넣지 말고 Secrets에 둡니다.

## 자주 보는 오류

| reason | 의미 | 대응 |
| --- | --- | --- |
| `missing_api_key` | API 키가 설정되지 않음 | channel별 API 키 이름과 Secrets 등록 여부를 확인합니다. |
| `api_key_rejected` | provider가 키를 거부함 | 키 만료, 권한, 결제 상태를 확인합니다. |
| `insufficient_balance` | 잔액 부족 | provider 콘솔에서 잔액 또는 결제 수단을 확인합니다. |
| `quota_exceeded` | 사용량 한도 초과 | 한도 상향, fallback channel, 사용량 제한을 검토합니다. |
| `rate_limit` | RPM 또는 TPM 제한 | 요청 간격을 늘리거나 더 낮은 빈도의 모델로 fallback합니다. |
| `timeout` | provider 응답 지연 | Base URL, 네트워크, timeout 값을 확인합니다. |
| `dns_error` | 도메인 해석 실패 | Base URL 오타와 실행 환경의 DNS 설정을 확인합니다. |
| `tls_error` | TLS 인증 문제 | HTTPS 인증서, 프록시, 보안 장비를 확인합니다. |
| `connection_refused` | endpoint 연결 거부 | 서버 실행 상태와 방화벽을 확인합니다. Ollama는 로컬 실행 여부를 확인합니다. |
| `endpoint_not_found` | endpoint 경로가 맞지 않음 | Base URL에 `/v1` 또는 provider별 API prefix가 필요한지 확인합니다. |
| `model_access_denied` | 모델 접근 권한 없음 | provider 콘솔에서 모델 권한과 allowlist를 확인합니다. |
| `provider_prefix_mismatch` | LiteLLM provider prefix 불일치 | `openai/<model>` 같은 prefix 형식을 맞춥니다. |
| `non_json` | JSON이 아닌 응답 수신 | Base URL이 API endpoint가 아닌 웹 페이지를 가리키는지 확인합니다. |
| `null_content` | 응답 본문에 content가 없음 | 모델의 tool, stream, JSON 모드 지원 여부를 확인합니다. |
| `capability_unsupported` | 요청한 기능 미지원 | JSON, tools, stream, vision 지원 범위를 provider별로 확인합니다. |
| `unknown_error` | 분류되지 않은 오류 | 로그의 provider 응답 메시지와 HTTP status를 함께 확인합니다. |

## 운영 권장 사항

- provider별 API 키는 channel 단위로 분리합니다.
- 기본 분석 모델과 Agent 모델은 같은 provider로 시작하고, 안정화 후 fallback을 추가합니다.
- 무료 또는 preview 모델은 연결 테스트가 성공해도 실제 분석에서 제한될 수 있습니다.
- OpenAI 호환 provider는 `/models` endpoint 지원 여부가 다르므로, 연결 테스트와 실제 분석 테스트를 모두 확인합니다.
- Ollama는 GitHub-hosted runner에서 사용할 수 없으므로 로컬 또는 self-hosted runner에서만 활성화합니다.
- provider 설정을 바꾼 뒤에는 `python -m pytest tests/test_llm_channel_config.py tests/test_system_config_service.py -q`로 설정 파싱 회귀를 확인합니다.

## 참고 링크

- LiteLLM: https://docs.litellm.ai/
- OpenAI platform docs: https://platform.openai.com/docs
- Gemini API docs: https://ai.google.dev/gemini-api/docs
- Anthropic docs: https://docs.anthropic.com/
- DeepSeek API docs: https://api-docs.deepseek.com/
