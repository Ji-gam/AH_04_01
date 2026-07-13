"""임시 개발용 DB 뷰어. ENV=local에서만 마운트된다.

app 본체와 동일한 engine(DB_HOST=mysql, 즉 docker mysql 컨테이너)을 그대로 재사용하므로
로컬이 아니라 docker-compose의 mysql 컨테이너 내용을 그대로 보고 고친다.

app/models 아래 전체 모듈을 자동 import해서 Base.registry에 매핑된 테이블을 전부
순회하며 뷰를 만들기 때문에, 새 모델 파일이 추가돼도 이 파일을 건드릴 필요가 없다.
비밀번호 컬럼도 해시값 그대로 노출하고(마스킹 없음), JSON 컬럼은 상세 화면에서
들여쓴 멀티라인으로 펼쳐서 보여준다. 필요 없어지면 이 파일과 app/main.py의
register_admin(app) 호출 한 줄만 지우면 된다.
"""

import importlib
import json
import pkgutil
import types
from typing import Any

from fastapi import FastAPI
from jinja2 import ChoiceLoader, DictLoader
from markupsafe import Markup, escape
from sqladmin import Admin, ModelView
from sqlalchemy import JSON

import app.models as models_pkg
from app.core.db.databases import engine
from app.models.base import Base

# sqladmin의 기본 list.html을 확장해서 행 전체를 클릭하면 상세화면으로 이동하게 만든다.
# 별도 템플릿 파일 없이 DictLoader로 문자열 템플릿을 등록 — 이 파일 하나로 끝내기 위함.
_LIST_TEMPLATE_OVERRIDE = """
{% extends "sqladmin_original/list.html" %}
{% block content %}
{{ super() }}
<style>
  table.table-vcenter tbody tr[data-row-clickable] { cursor: pointer; }
</style>
<script>
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("table tbody tr").forEach(function (row) {
      var viewLink = row.querySelector('a[href*="/details/"]');
      if (!viewLink) return;
      row.setAttribute("data-row-clickable", "");
      row.addEventListener("click", function (event) {
        if (event.target.closest("a, input, button")) return;
        window.location = viewLink.getAttribute("href");
      });
    });
  });
</script>
{% endblock %}
"""


def _import_all_model_modules() -> None:
    """app/models 아래 모든 모듈을 import해서 __init__.py에 안 걸려 있는 모델도 Base.registry에 매핑되게 한다."""
    for module_info in pkgutil.iter_modules(models_pkg.__path__, prefix=f"{models_pkg.__name__}."):
        importlib.import_module(module_info.name)


def _pretty_json(obj: Any, attr: str) -> Any:
    value = getattr(obj, attr)
    if value is None:
        return ""
    dumped = json.dumps(value, indent=2, ensure_ascii=False)
    return Markup("<pre style='white-space:pre-wrap;margin:0'>{}</pre>").format(escape(dumped))


def _column_label(column: Any) -> str:
    tags = []
    if column.primary_key:
        tags.append("PK")
    if column.foreign_keys:
        tags.append("FK")
    return f"{column.name} ({'/'.join(tags)})" if tags else column.name


def _build_view(model: type[Any]) -> type[ModelView]:
    table_columns = model.__table__.columns
    columns = [c.name for c in table_columns]
    json_columns = [c.name for c in table_columns if isinstance(c.type, JSON)]

    def exec_body(namespace: dict[str, Any]) -> None:
        namespace.update(
            column_list=columns,
            column_details_list=columns,
            form_columns=columns,
            column_labels={c.name: _column_label(c) for c in table_columns},
            column_formatters_detail={name: _pretty_json for name in json_columns},
            can_create=True,
            can_edit=True,
            can_delete=True,
            can_view_details=True,
            page_size=100,
            name_plural=model.__tablename__,
        )

    return types.new_class(f"{model.__name__}AutoAdminView", (ModelView,), {"model": model}, exec_body)


def register_admin(app: FastAPI) -> None:
    _import_all_model_modules()

    admin = Admin(app, engine, title="DB Raw Viewer (docker mysql, local only)")
    existing_loader = admin.templates.env.loader
    assert existing_loader is not None
    admin.templates.env.loader = ChoiceLoader(
        [DictLoader({"sqladmin/list.html": _LIST_TEMPLATE_OVERRIDE}), existing_loader]
    )

    mapped_models = sorted(Base.registry.mappers, key=lambda m: m.class_.__tablename__)
    for mapper in mapped_models:
        admin.add_view(_build_view(mapper.class_))
