"""API 명세서 + ERD 자동 생성기.

코드(FastAPI 라우터 / SQLAlchemy 모델)를 유일한 진실로 삼아 아래 3개 문서를 다시 만든다.

  - docs/dev/api_spec_v1.yaml : 런타임 OpenAPI 스키마 전체
  - docs/dev/API_SPEC.md      : 엔드포인트 요약표(태그별)
  - docs/dev/ERD.dbml         : dbdiagram.io용 ERD

사용법 (레포 루트에서):
    python scripts/gen_api_docs.py

엔드포인트/모델을 추가·변경했으면 같은 PR에서 이 스크립트를 돌려 문서를 갱신한다
(AGENTS.md §8, docs/CODING_RULES.md §6).
"""

import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.models  # noqa: F401,E402  (전 모델 임포트로 metadata 채움)
from app.main import app as fastapi_app  # noqa: E402
from app.models.base import Base  # noqa: E402

DEV_DOCS = ROOT / "docs" / "dev"
OUT_DBML = DEV_DOCS / "ERD.dbml"
OUT_YAML = DEV_DOCS / "api_spec_v1.yaml"
OUT_MD = DEV_DOCS / "API_SPEC.md"
TODAY = date.today().isoformat()


def col_type(c):
    try:
        t = c.type.compile(dialect_name="mysql")
    except Exception:
        t = str(c.type)
    t = t.lower()
    t = t.replace("integer", "int").replace("bigint", "bigint")
    if t.startswith("enum"):
        t = "varchar(30)"
    return t


def esc(s):
    return str(s).replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ").strip()


def default_of(c):
    d = c.server_default
    if d is not None and getattr(d, "arg", None) is not None:
        txt = str(d.arg)
        if "CURRENT_TIMESTAMP" in txt.upper() or "now()" in txt:
            return "`CURRENT_TIMESTAMP`"
        if txt.replace("_", "").isalnum() and not txt.isdigit():
            return f"'{esc(txt)}'"
        return f"`{txt}`"
    if c.default is not None and getattr(c.default, "is_scalar", False):
        v = c.default.arg
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, (int, float)):
            return str(v)
        return f"'{esc(v)}'"
    return None


# (TableGroup 슬러그, 섹션 제목, 테이블 목록) — 목록이 None이면 "나머지 전부"
GROUPS = [
    ("account_auth", "계정 · 인증", ["users", "profiles", "issued_refresh_tokens", "withdrawn_health_stats"]),
    ("family", "가족 연동", ["family_links", "family_invite_codes"]),
    ("health_profile", "건강 프로필 · 문진", ["diagnosis_entries", "disease_subtypes", "family_history_entries"]),
    (
        "medication",
        "복약",
        ["medication_schedules", "medication_intake_logs", "medication_recognition_jobs", "medication_data_cache"],
    ),
    (
        "lifelog_goal",
        "생활기록 · 목표",
        [
            "diary_entries",
            "diet_logs",
            "exercise_logs",
            "sleep_logs",
            "habit_logs",
            "habit_selections",
            "habit_subtype_suggestions",
            "goals",
            "goal_progress_logs",
            "weekly_reports",
        ],
    ),
    ("chat_content", "챗봇 · 콘텐츠", ["chat_sessions", "chat_messages", "health_contents", "notices"]),
    (
        "notification",
        "알림 · 푸시",
        [
            "notification_schedules",
            "notification_settings",
            "notification_logs",
            "push_subscriptions",
            "push_send_logs",
        ],
    ),
    ("ops_log", "운영 · 로그", ["admin_actions", "error_logs"]),
    ("drug_reference", "외부 의약품/식품 참조데이터 (DUR·식약처 캐시)", None),
]


def render_column(t, c):
    attrs = []
    if c.primary_key:
        attrs.append("pk")
        if c.autoincrement is True or (
            c.autoincrement == "auto" and len(t.primary_key.columns) == 1 and "int" in col_type(c)
        ):
            attrs.append("increment")
    if not c.nullable and not c.primary_key:
        attrs.append("not null")
    if c.unique:
        attrs.append("unique")
    d = default_of(c)
    if d:
        attrs.append(f"default: {d}")
    for fk in c.foreign_keys:
        attrs.append(f"ref: > {fk.target_fullname}")
    if c.comment:
        attrs.append(f"note: '{esc(c.comment)}'")
    a = f" [{', '.join(attrs)}]" if attrs else ""
    return f"  {c.name} {col_type(c)}{a}"


def render_table(t):
    lines = [f"Table {t.name} {{"]
    lines += [render_column(t, c) for c in t.columns]

    idx = list(t.indexes)
    multi_uc = [cst for cst in t.constraints if cst.__class__.__name__ == "UniqueConstraint" and len(cst.columns) > 1]
    if idx or multi_uc:
        lines.append("")
        lines.append("  indexes {")
        for cst in multi_uc:
            cols = ", ".join(c.name for c in cst.columns)
            lines.append(f"    ({cols}) [unique]")
        for i in sorted(idx, key=lambda x: x.name or ""):
            cols = ", ".join(c.name for c in i.columns)
            flag = " [unique]" if i.unique else ""
            lines.append(f"    ({cols}){flag}")
        lines.append("  }")
    if t.comment:
        lines.append("")
        lines.append(f"  Note: '{esc(t.comment)}'")
    lines.append("}")
    return "\n".join(lines)


def gen_dbml():
    md = Base.metadata
    all_names = set(md.tables)
    assigned = set()
    out = []
    n_tables = len(all_names)
    header = f"""// AH_04_01 (ReMedi) ERD — dbdiagram.io (https://dbdiagram.io)에 그대로 붙여넣어 보면 됩니다.
//
// 문서 버전: v2.0 · 최종 수정: {TODAY}
// 생성 방식: SQLAlchemy 모델(app/models/*.py) 기준으로 추출 — 코드가 유일한 진실
// 변경 이력:
//   - v1.0~v1.3 (2026-07-07~08): 수기 작성 (users/profiles/chat/notification_schedules/health_contents)
//   - v2.0 ({TODAY}): 전체 재작성. 현재 매핑된 {n_tables}개 테이블(복약/생활기록/목표/가족연동/알림/운영로그/
//     DUR·식약처 참조데이터) 전부 반영.
//
// 규칙 (docs/CODING_RULES.md 6번):
//   DB를 CRUD하는 작업(모델 추가/변경, 마이그레이션 작성)을 할 때마다 이 파일도 같은 커밋/PR에서
//   함께 갱신하고 위 버전을 올린다. 신규 도메인 테이블은 user_id가 아니라 profiles.id를 참조한다.
"""
    out.append(header)

    for _slug, title, names in GROUPS:
        if names is None:
            names = sorted(all_names - assigned)
        else:
            names = [n for n in names if n in all_names]
        if not names:
            continue
        assigned |= set(names)
        out.append(f"\n// ==================== {title} ====================\n")
        for n in names:
            out.append(render_table(md.tables[n]))
            out.append("")

    out.append("\n// ==================== 논리 그룹 ====================\n")
    for slug, _title, names in GROUPS:
        if names is None:
            names = sorted(all_names - set().union(*[set(g[2] or []) for g in GROUPS if g[2]]))
        names = [n for n in names if n in all_names]
        if not names:
            continue
        body = "\n".join(f"  {n}" for n in names)
        out.append(f"TableGroup {slug} {{\n{body}\n}}\n")
    return "\n".join(out)


def gen_openapi():
    spec = fastapi_app.openapi()
    spec["info"]["title"] = "ReMedi API v1"
    spec["info"]["version"] = "1.0.0"
    spec["info"]["description"] = (
        "AH_04_01(ReMedi) 백엔드 전체 API 명세.\n\n"
        "- 생성 방식: FastAPI 앱(`app/main.py`)의 런타임 OpenAPI 스키마를 추출 — 코드가 유일한 진실.\n"
        "- 인증: JWT (`Authorization: Bearer <access_token>`), Access 30분 / Refresh 14일.\n"
        "- 도메인 데이터는 `user_id`가 아니라 `profile_id` 기준으로 스코핑한다.\n"
        "- 갱신: `python scripts/gen_api_docs.py` (엔드포인트 추가/변경 시 같은 PR에서 재생성).\n"
    )
    spec["servers"] = [
        {"url": "http://localhost:8000", "description": "로컬 개발"},
        {"url": "https://api.remedi.app", "description": "운영(예정)"},
    ]
    return spec


# ---------- 엔드포인트 요약 마크다운 ----------
def gen_md(spec):
    by_tag = {}
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            tag = (op.get("tags") or ["기타"])[0]
            auth = "O" if op.get("security") else ""
            by_tag.setdefault(tag, []).append((method.upper(), path, op.get("summary", "").strip(), auth))
    total = sum(len(v) for v in by_tag.values())
    lines = [
        "# ReMedi API 명세 요약 (v1)",
        "",
        f"- 생성 방식: FastAPI 런타임 OpenAPI 추출 · 최종 갱신 {TODAY} · 총 {total}개 엔드포인트",
        "- 전체 스키마(요청/응답 본문, 필드 설명): [`api_spec_v1.yaml`](api_spec_v1.yaml)",
        "  · Swagger UI: 로컬 실행 후 <http://localhost:8000/docs>",
        "- 인증: `Authorization: Bearer <access_token>` (Access 30분 / Refresh 14일)",
        "- 도메인 데이터 스코핑 기준은 `user_id`가 아니라 `profile_id`",
        "- ERD: [`ERD.dbml`](ERD.dbml) (dbdiagram.io에 붙여넣기)",
        "- 재생성: `python scripts/gen_api_docs.py` — 엔드포인트/모델 변경 시 같은 PR에서 함께 갱신",
        "- `api_spec_core_v1_v1.1.yaml`은 Phase 1 설계 단계의 수기 초안으로, 위 문서로 대체됨(참고용)",
        "",
    ]
    for tag in sorted(by_tag):
        lines.append(f"## {tag}")
        lines.append("")
        lines.append("| Method | Path | 설명 | 인증 |")
        lines.append("| --- | --- | --- | --- |")
        for m, p, s, a in sorted(by_tag[tag], key=lambda x: (x[1], x[0])):
            lines.append(f"| `{m}` | `{p}` | {s} | {a} |")
        lines.append("")
    return "\n".join(lines)


def main():
    spec = gen_openapi()
    OUT_DBML.write_text(gen_dbml(), encoding="utf-8")
    with OUT_YAML.open("w", encoding="utf-8") as f:
        f.write("# 자동 생성 파일 — 직접 수정하지 말고 `python scripts/gen_api_docs.py`로 재생성하세요.\n")
        yaml.safe_dump(spec, f, allow_unicode=True, sort_keys=False, width=120)
    OUT_MD.write_text(gen_md(spec), encoding="utf-8")
    for p in (OUT_YAML, OUT_MD, OUT_DBML):
        print(f"generated {p.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
