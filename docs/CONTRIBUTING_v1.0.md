# AH_04_01 협업 하네스 (최소 버전)

> 목적: 여러 장소에서, 스쿼드별로 나눠서, 개발 초보자들이 참여하는 프로젝트에서
> "서로 꼬이지 않는 것"에만 집중한 최소 규칙입니다. 완벽한 프로세스가 아니라
> **사고를 줄이는 최소 장치**라고 생각하고 팀 상황에 맞게 가감하세요.
>
> **문서 버전**: v1.0 · **최종 수정**: 2026-07-07
> **변경 이력**
> - v1.0 (2026-07-07): `remedi_mweb_co`에서 이식하며 레포 구조를 `AH_04_01`의 실제 최상위 폴더(`app/`, `ai_worker/`, `frontend/`, `envs/`, `infra/`, `scripts/`)로 수정

---

## 0. 한 장 요약

| 항목 | 규칙 |
| --- | --- |
| 레포 | 모노레포 1개 (`frontend/`, `app/` — `app`은 레이어 우선 구조) |
| 브랜치 | `main`(배포) ← `dev`(통합) ← `feature/T-ID-설명`(작업), 필요 시 `Release`, `hotfix/*` |
| 커밋 | `type(T-ID): 설명` 예) `feat(T-AUTH-1): 이메일 회원가입 API` |
| PR | 작은 단위, 제목에 T-ID/F-ID, 리뷰 1명 필수, `dev`로 머지 |
| 이슈 | 제목에 T-ID 포함, 담당 스쿼드 라벨 지정 |
| 충돌 방지 | 작업 시작 전 슬랙에 "지금 어떤 파일/기능 건드림" 1줄 공지 |
| 하루 루틴 | 시작 시 `git pull`, 끝날 때 push + PR, 자기 전 dev 최신화 |

---

## 1. 레포 구조 (모노레포)

```
AH_04_01/
├─ app/                  # 백엔드 (레이어 우선 구조 — 상세는 CODING_RULES_v1.0.md 2번)
│  ├─ apis/ services/ repositories/ models/ dtos/ core/ dependencies/ tests/
├─ ai_worker/            # AI/RAG/멀티모달 추론 — 메인 API 프로세스와 분리된 별도 서비스
├─ frontend/             # 프론트엔드 (React + Vite, pages/ 구조 — FRONTEND_ARCHITECTURE_v1.0.md)
├─ envs/                 # 환경별 설정 파일 (CODING_RULES_v1.0.md 2-2 참고)
├─ infra/                # nginx, 배포 관련 설정
├─ scripts/              # 배포/CI 보조 스크립트 (ruff/mypy/pytest 로컬 실행용)
├─ docs/
│  ├─ PRD_ReMedi_v1.1.md / TRD_ReMedi_v1.1.md
│  ├─ CODING_RULES_v1.0.md / FRONTEND_ARCHITECTURE_v1.0.md / decision_log_v1.0.md
│  ├─ squad-map_v1.0.md        # 아래 2번 내용
│  ├─ ERD_v1.0.dbml            # DB 스키마 최신 상태 (CODING_RULES_v1.0.md 6번)
│  └─ sample_code_chat/, sample_code_recog/   # 실제로 동작하는 템플릿 코드
└─ CLAUDE.md              # Claude(Code) 등 AI 에이전트가 지켜야 할 규칙
```

**모노레포를 쓰는 이유**: 초보 개발자 팀에서 레포가 나뉘면 "API 스펙이 바뀌었는데 프론트가 몰랐다"는 문제가 반드시 생깁니다. 하나의 레포 + 하나의 PR 흐름이면 리뷰할 때 프론트/백엔드 변경을 같이 볼 수 있어 훨씬 안전합니다.

---

## 2. 스쿼드 ↔ 기능 도메인 매핑

TRD의 T-그룹 경계를 그대로 스쿼드 경계로 씁니다. 이렇게 하면 "이 파일은 누구 담당인지"를 이슈 번호만 보고 알 수 있습니다. 실제 담당자 배정은 `squad-map_v1.0.md`에 채웁니다.

- **레이어 우선 구조라 폴더가 아니라 파일명으로 소유권을 나눕니다**: 도메인 하나의 코드가 `apis/`, `services/`, `repositories/`, `models/`, `dtos/`에 흩어져 있으므로, "이 폴더는 내 것"이 아니라 "이 접두어가 붙은 파일은 내 것"으로 구분하세요 (`CODING_RULES_v1.0.md` 2번 참고).
- 접두어는 첫 스프린트 킥오프 때 실제 도메인 이름에 맞게 `squad-map_v1.0.md`에 확정해서 적어두세요.

---

## 3. 브랜치 전략 (GitFlow)

```
main   ← 배포 가능한 최종 상태만 (직접 push 금지, PR로만 병합)
 └─ dev ← 개발 중인 기능이 모이는 통합 브랜치 (직접 push 금지, PR로만 병합)
     ├─ feature/{T-ID}-{짧은설명}   ← dev에서 분기, dev로 병합
     ├─ Release/{버전}              ← dev에서 분기, main + dev 양쪽에 병합
     └─ hotfix/{짧은설명}           ← main에서 분기, main + dev 양쪽에 병합
```

- 브랜치 예: `feature/T-MED-1-pill-recognition`, `hotfix/login-token-expire-crash`
- 초보 팀은 대부분 `feature/*`만 씁니다.
- **main, dev는 보호 브랜치로 설정**하고, 반드시 PR + 최소 1명 승인 후에만 병합되게 하세요.
- `feature/*`는 항상 **`dev`를 최신으로 pull한 뒤** 분기하세요.

---

## 4. 커밋 & PR 규칙

### 커밋 메시지
```
type(T-ID): 설명

예)
feat(T-AUTH-1): 이메일 회원가입 API 구현
fix(T-NTFY-1): 알림 미도착 버그 수정
docs(T-LLM-1): 면책조항 정책 문서 추가
```

### PR 규칙
- 제목: `[T-ID] 작업 내용 요약`
- 설명에 최소 포함: 무엇을 했는지(TRD 성공요건 충족 여부 체크), 어떻게 테스트했는지
- **200~300줄 이내로 작게** 쪼개서 올리기
- 리뷰어 1명 승인 후 본인이 머지, **Squash and merge**로 통일
- DB를 CRUD하는 PR은 `docs/ERD_v1.0.dbml`도 같이 갱신했는지 확인 (`CODING_RULES_v1.0.md` 6번)

---

## 5. 이슈 관리

- 이슈 제목에 반드시 T-ID/F-ID 포함
- 라벨: 스쿼드명, 상태(`todo`/`in-progress`/`review`/`done`)
- 담당자 지정 없이 작업 시작 금지

---

## 6. 충돌(코드/작업) 방지 원칙

| 문제 상황 | 예방 규칙 |
| --- | --- |
| 같은 파일을 두 사람이 동시에 수정 | 작업 시작 전 슬랙/디스코드에 "지금 `medication/schedule.ts` 건드립니다" 한 줄 공지 |
| 공통 모듈(`services/`의 4개 공통모듈 등)을 바꿨는데 다른 스쿼드가 모름 | 공통모듈 변경 PR은 팀 전체 채널에 별도 공지 + 다른 스쿼드 리뷰 필수 |
| 오래된 브랜치에서 작업해서 충돌 폭탄 | 매일 작업 시작 전 `git checkout dev && git pull` 후 새로 브랜치 따기 습관화 |
| dev에 머지했는데 깨짐 | 머지 전 로컬에서 `scripts/ci/run_test.sh`, `scripts/ci/code_fommatting.sh` 실행 확인 |

---

## 7. 환경변수 / 시크릿

- 실제 값이 든 `.env`, `envs/.local.env`, `envs/.prod.env`는 절대 커밋 금지.
- API 키는 슬랙 DM이나 비공개 페이지로 공유, **절대 PR/이슈/코드에 평문으로 남기지 않기**

---

## 8. 다음에 정할 것 (킥오프 때 채우기)

- [ ] `docs/squad-map_v1.0.md`에 실제 스쿼드 이름 + 담당 T-ID 확정
- [ ] GitHub 브랜치 보호 규칙 설정 (main, dev)
- [ ] 이슈 라벨 생성 (스쿼드별 + 상태별)
- [ ] `.github/workflows/ci.yml` 등록 (`scripts/ci/*.sh`를 CI에서도 동일하게 실행)
