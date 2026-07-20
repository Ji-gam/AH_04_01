# 웹푸시(Web Push) - 1단계 구현 (임시 스케줄러 방식)

지난번에 논의했던 "복약알림이 탭을 닫아도 울리게" 하는 웹푸시 기능입니다.
**마이그레이션 있음(0021)** - `docker compose exec fastapi uv run alembic upgrade head` 필요.

## ⚠️ 시작하기 전에 꼭 해야 할 것 2가지

### 1. `uv.lock` 갱신 (의존성 추가함)
`pywebpush`, `apscheduler`를 `pyproject.toml`에 추가했는데, `app/Dockerfile`이
`uv sync --frozen`(잠금파일과 정확히 일치해야만 성공)을 쓰기 때문에 **로컬에서 먼저
락파일을 갱신**해야 도커 빌드가 됩니다:
```powershell
uv lock
```
(`--frozen` 없이 `uv sync`만 해도 됩니다 - 락파일이 자동 갱신됨)

### 2. VAPID 키 생성 (1회만)
```powershell
uv run python app/scripts/generate_vapid_keys.py
```
출력되는 두 줄을 `.env`에 그대로 붙여넣으세요:
```
VAPID_PUBLIC_KEY=...
VAPID_PRIVATE_KEY=...
```
**이 키는 한 번 만들면 계속 재사용**하세요 - 나중에 다시 생성하면 그전까지 쌓인 모든
브라우저 구독이 전부 무효화됩니다(사용자들이 "알림 켜기"를 다시 눌러야 함).

## 1. 파일 어디에 넣는지

| 경로 | 상태 | 비고 |
|---|---|---|
| `pyproject.toml` | 덮어쓰기 | `pywebpush`, `apscheduler` 추가 |
| `app/core/config.py` | 덮어쓰기 | `VAPID_PUBLIC_KEY`/`VAPID_PRIVATE_KEY`/`VAPID_CLAIM_EMAIL` 설정 추가 |
| `app/core/db/migrations/versions/0021_add_push_subscriptions.py` | 신규 | `push_subscriptions` 테이블 |
| `app/models/push_subscription.py` | 신규 | `PushSubscription` 모델 (platform 컬럼 - 나중에 앱 패키징 시 IOS/ANDROID 확장용) |
| `app/models/__init__.py` | 덮어쓰기 | 모델 등록 |
| `app/dtos/push.py` | 신규 | 구독/해제 요청 DTO |
| `app/repositories/push_subscription_repository.py` | 신규 | |
| `app/services/push_service.py` | 신규 | 구독 저장 + 실제 발송(`pywebpush`) |
| `app/services/push_scheduler.py` | 신규 | **임시 스케줄러** (아래 설명) |
| `app/apis/v1/push_routers.py` | 신규 | `/push/vapid-public-key`, `/push/subscribe`, `/push/unsubscribe` |
| `app/apis/v1/__init__.py` | 덮어쓰기 | 라우터 등록 |
| `app/main.py` | 덮어쓰기 | `lifespan`에 스케줄러 시작/종료 추가 |
| `app/scripts/generate_vapid_keys.py` | 신규 | VAPID 키 생성용 1회성 스크립트 |
| `frontend/public/service-worker.js` | 신규 | 백그라운드에서 push 이벤트 받아 알림 띄우는 서비스워커 |
| `frontend/src/api/pushApi.ts` | 신규 | |
| `frontend/src/utils/webPush.ts` | 신규 | 구독/해제 유틸(`enableWebPush`/`disableWebPush`) |
| `frontend/src/pages/AlarmPage/AlarmPage.tsx` | 덮어쓰기 | "🔔 알림 켜기" 배너 추가(구독 안 돼있을 때만 노출) |

## 2. ⚠️ "임시 구현"인 이유 - 꼭 읽어주세요

**정확한 시간에 실제로 발송을 트리거하는 부분이 `celery-beat`가 아니라 APScheduler로
fastapi 프로세스 안에서 도는 방식**입니다. 원래는 `docker-compose.yml`에
`celery-worker`/`celery-beat` 서비스를 추가해서 그쪽에서 도는 게 정석인데, 그 파일은
`app/core/celery_app.py`에 이미 "리더 소유 파일이라 리더가 직접 진행"이라고 적혀있어서,
지금 당장 웹푸시를 살리려고 **fastapi 프로세스 안에서 1분마다 도는 APScheduler**로 우회
구현했습니다.

**알려진 한계**:
- uvicorn을 여러 워커/레플리카로 띄우면 이 스케줄러가 워커 개수만큼 중복으로 돌아서 **같은
  알림이 여러 번 발송될 수 있습니다.** 지금은 로컬/개발 환경(워커 1개) 기준입니다.
- 나중에 리더분이 `celery-beat`을 붙이시면, `app/services/push_scheduler.py`의
  `_check_and_send_due_notifications()` 내용을 그대로 celery task로 옮기고 이 스케줄러는
  빼는 게 정석입니다.

## 3. 앱(네이티브) 패키징 고려사항

`PushSubscription` 모델에 `platform` 컬럼(WEB/IOS/ANDROID)을 미리 넣어뒀습니다. 지금은
WEB만 실제로 씁니다. 나중에 Capacitor로 패키징할 때:
- iOS/Android 쪽에서 Capacitor Push Notifications 플러그인으로 받은 디바이스 토큰을
  같은 테이블의 `device_token` 컬럼에 저장하면 됩니다(테이블 새로 안 만들어도 됨)
- `push_service.py`의 `send_to_profile()`에 platform별 분기(APNs/FCM 발송)만 추가하면 됨

## 4. 테스트한 것

- VAPID 키 생성 스크립트 실제 실행 확인 (공개키/개인키 생성 + `pywebpush`가 그 형식을
  실제로 파싱해서 서명까지 되는지 end-to-end 확인)
- SQLite로 구독 생성/중복처리/목록조회/삭제 확인
- 요일 판정 로직(`_is_due_today`) - DAILY/WEEKLY 케이스, 프론트(`dateUtils.ts`)와 동일한
  기준으로 맞춰서 검증
- 프론트 `tsc`/`eslint`/`prettier`/`vitest` 전부 통과

**실제 브라우저에서 알림이 뜨는지는 아직 직접 눌러보지 못했습니다** - VAPID 키 설정하시고
"🔔 알림 켜기" 눌러서 브라우저 알림 허용하신 다음, 아래 순서로 확인해주세요.

## 5. 화면에서 확인하는 법

1. 위 "시작하기 전에" 2가지(`uv lock`, VAPID 키) 먼저 처리
2. `docker compose exec fastapi uv run alembic upgrade head`
3. `docker compose up -d --build` (또는 로컬 재시작)
4. 복약알림 화면에서 "🔔 알림 켜기" 클릭 → 브라우저 알림 권한 허용
5. 알림 하나를 **지금 시각 + 1~2분 후**로 등록 (예: 지금이 14:03이면 14:05로)
6. **탭을 닫거나 다른 화면으로 이동**한 채로 기다렸다가, 설정한 시각에 OS 알림(Windows
   알림센터 등)이 뜨는지 확인
7. 로그(`docker compose logs fastapi`)에서 "푸시 스케줄러 시작됨" 메시지 확인 가능
