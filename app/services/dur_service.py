from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dtos.dur_dto import (
    BasicScreeningResponse,
    BasicScreeningResult,
    DrugDetail,
    DrugIdentification,
    DrugIntrc,
    DrugRef,
    DurInteractionWarning,
    DurSimpleFlag,
    IngredientDetail,
    IngredientRuleDetail,
    IngredientScreeningResponse,
    IngredientSourceDrug,
    InteractionScreeningResponse,
    RecallInfo,
)
from app.repositories.dur_repository import SINGLE_DRUG_RULE_TABLES, DurScreeningRepository


def _build_dur_simple(item_seq: str, rules_raw: list[dict]) -> list[DurSimpleFlag]:
    """rule_code별로 항상 6개 고정 순서(SINGLE_DRUG_RULE_TABLES 순서)로 내려간다. 같은 rule_code에
    행이 여러 개(조합 파트너별 반복 저장) 있으면 첫 번째 것만 대표값으로 쓴다 - 전체 변형은 3단계
    성분 상세에서 확인 가능."""
    first_hit_by_code: dict[str, dict] = {}
    for r in rules_raw:
        if r["item_seq"] != item_seq:
            continue
        first_hit_by_code.setdefault(r["rule_code"], r)

    return [
        DurSimpleFlag(
            rule_code=code,
            rule_label=label,
            present=code in first_hit_by_code,
            prohbt_content=(first_hit_by_code[code]["prohbt_content"] or None) if code in first_hit_by_code else None,
            remark=(first_hit_by_code[code]["remark"] or None) if code in first_hit_by_code else None,
        )
        for _table, code, label in SINGLE_DRUG_RULE_TABLES
    ]


def _build_usjnt_warnings(rows: list[dict], seen_pairs: set[frozenset[str]]) -> list[DurInteractionWarning]:
    warnings = []
    for u in rows:
        pair = frozenset({u["item_seq"], u["mixture_item_seq"]})
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        warnings.append(
            DurInteractionWarning(
                rule_type="병용금기",
                drug_a=DrugRef(item_seq=u["item_seq"], item_name=u["item_name"]),
                drug_b=DrugRef(item_seq=u["mixture_item_seq"], item_name=u["mixture_item_name"]),
                prohbt_content=u["prohbt_content"] or None,
                remark=u["remark"] or None,
            )
        )
    return warnings


def _build_efficacy_warnings(rows: list[dict], seen_pairs: set[frozenset[str]]) -> list[DurInteractionWarning]:
    groups: dict[str, dict] = {}
    for e in rows:
        group = groups.setdefault(e["ingr_code"], {"drugs": [], "content": e["prohbt_content"], "remark": e["remark"]})
        if not any(d["item_seq"] == e["item_seq"] for d in group["drugs"]):
            group["drugs"].append({"item_seq": e["item_seq"], "item_name": e["item_name"]})

    warnings = []
    for group in groups.values():
        drugs = group["drugs"]
        for i in range(len(drugs)):
            for j in range(i + 1, len(drugs)):
                pair = frozenset({drugs[i]["item_seq"], drugs[j]["item_seq"]})
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                warnings.append(
                    DurInteractionWarning(
                        rule_type="효능군중복주의",
                        drug_a=DrugRef(**drugs[i]),
                        drug_b=DrugRef(**drugs[j]),
                        prohbt_content=group["content"] or None,
                        remark=group["remark"] or None,
                    )
                )
    return warnings


class DurScreeningService:
    def __init__(self, repository: DurScreeningRepository | None = None):
        # 테스트에서 mock 리포지토리를 주입할 수 있도록 허용
        self._repository = repository

    def _get_repo(self, session: AsyncSession) -> DurScreeningRepository:
        return self._repository or DurScreeningRepository(session)

    def _validate_and_dedupe(self, drug_names: list[str]) -> list[str]:
        unique_names = list(dict.fromkeys(name.strip() for name in drug_names if name.strip()))
        if not unique_names:
            raise HTTPException(status_code=400, detail="약품명을 1개 이상 입력해주세요")
        return unique_names

    async def screen_basic(self, session: AsyncSession, drug_names: list[str]) -> BasicScreeningResponse:
        unique_names = self._validate_and_dedupe(drug_names)
        repo = self._get_repo(session)
        matched, unmatched = await repo.resolve_item_seqs(unique_names)

        if not matched:
            return BasicScreeningResponse(results=[], unmatched_drug_names=unmatched)

        item_seqs = [d["item_seq"] for d in matched]
        rules_raw = await repo.get_single_drug_rules(item_seqs)

        identification_by_seq: dict[str, dict] = {}
        for i in await repo.get_drug_identification(item_seqs):
            identification_by_seq.setdefault(i["item_seq"], i)

        safety_by_seq: dict[str, dict] = {}
        for s in await repo.get_drug_safety_info(item_seqs):
            safety_by_seq.setdefault(s["item_seq"], s)

        results = []
        for d in matched:
            ident = identification_by_seq.get(d["item_seq"])
            safety = safety_by_seq.get(d["item_seq"])
            detail = DrugDetail(
                item_seq=d["item_seq"],
                item_name=d["item_name"],
                entp_name=d["entp_name"],
                etc_otc_name=ident["etc_otc_name"] if ident else None,
                form_name=ident["form_name"] if ident else None,
                efcy_qesitm=d["efcy_qesitm"],
                use_method_qesitm=d["use_method_qesitm"],
                atpn_warn_qesitm=d["atpn_warn_qesitm"],
                se_qesitm=d["se_qesitm"],
                deposit_method_qesitm=d["deposit_method_qesitm"],
                item_image=d["item_image"],
                identification=DrugIdentification(shape=ident["shape"], color=ident["color"], mark=ident["mark"])
                if ident
                else None,
                atc_code=safety["atc_code"] if safety else None,
                is_rare_drug=(safety["rare_drug_yn"] == "Y") if safety and safety["rare_drug_yn"] else None,
                narcotic_kind_name=(safety["narcotic_kind_name"] or None) if safety else None,
            )
            results.append(
                BasicScreeningResult(
                    drug_detail=detail,
                    dur_simple=_build_dur_simple(d["item_seq"], rules_raw),
                )
            )
        return BasicScreeningResponse(results=results, unmatched_drug_names=unmatched)

    async def screen_interactions(self, session: AsyncSession, drug_names: list[str]) -> InteractionScreeningResponse:
        unique_names = self._validate_and_dedupe(drug_names)
        repo = self._get_repo(session)
        matched, unmatched = await repo.resolve_item_seqs(unique_names)

        if not matched:
            return InteractionScreeningResponse(
                drug_intrc=DrugIntrc(interactions=[], recalls=[]), unmatched_drug_names=unmatched
            )

        item_seqs = [d["item_seq"] for d in matched]

        recalls = [
            RecallInfo(
                item_seq=r["item_seq"],
                item_name=r["item_name"],
                entp_name=r["entp_name"] or None,
                recall_reason=r["recall_reason"] or None,
                recall_command_date=r["recall_command_date"] or None,
                enforced=(r["enforced_yn"] == "Y") if r["enforced_yn"] else None,
            )
            for r in await repo.get_recalls(item_seqs)
        ]

        seen_pairs: set[frozenset[str]] = set()
        interactions = _build_usjnt_warnings(await repo.get_interactions_within_set(item_seqs), seen_pairs)
        interactions += _build_efficacy_warnings(await repo.get_efficacy_groups(item_seqs), seen_pairs)

        return InteractionScreeningResponse(
            drug_intrc=DrugIntrc(interactions=interactions, recalls=recalls),
            unmatched_drug_names=unmatched,
        )

    async def screen_ingredients(self, session: AsyncSession, drug_names: list[str]) -> IngredientScreeningResponse:
        unique_names = self._validate_and_dedupe(drug_names)
        repo = self._get_repo(session)
        matched, unmatched = await repo.resolve_item_seqs(unique_names)

        if not matched:
            return IngredientScreeningResponse(ingredients=[], unmatched_drug_names=unmatched)

        item_seqs = [d["item_seq"] for d in matched]
        seq_to_name = {d["item_seq"]: d["item_name"] for d in matched}

        ingr_codes_by_item = await repo.get_ingredient_codes_for_items(item_seqs)

        # ingr_code -> {item_seq -> (qnt, unit)} - set이 아니라 dict인 이유는 같은 성분이라도
        # 약마다 함량(qnt/unit)이 다를 수 있어 item_seq별로 따로 들고 있어야 하기 때문.
        source_items_by_ingr: dict[str, dict[str, tuple[str | None, str | None]]] = {}
        ingr_names: dict[str, str] = {}
        for seq, codes in ingr_codes_by_item.items():
            for code, name, qnt, unit in codes:
                source_items_by_ingr.setdefault(code, {})[seq] = (qnt, unit)
                if name:
                    ingr_names.setdefault(code, name)

        seen_ingr_rules: dict[str, set[tuple[str, str | None, str | None, str | None]]] = {}
        rules_by_ingr: dict[str, list[IngredientRuleDetail]] = {}
        for r in await repo.get_ingredient_level_rules(list(source_items_by_ingr.keys())):
            # 성분-조합 짝 단위로 저장된 원본이라 같은 (성분,규칙,내용) 조합이 반복되는 경우가 많다.
            key = (r["rule_type"], r["prohbt_content"] or None, r["remark"] or None, r["rule_detail"] or None)
            seen = seen_ingr_rules.setdefault(r["ingr_code"], set())
            if key not in seen:
                seen.add(key)
                rules_by_ingr.setdefault(r["ingr_code"], []).append(
                    IngredientRuleDetail(
                        rule_type=r["rule_type"],
                        prohbt_content=r["prohbt_content"] or None,
                        remark=r["remark"] or None,
                        rule_detail=r["rule_detail"] or None,
                    )
                )
            if r["ingr_name"]:
                ingr_names.setdefault(r["ingr_code"], r["ingr_name"])

        ingredients = [
            IngredientDetail(
                ingr_code=code,
                ingr_name=ingr_names.get(code, ""),
                source_drugs=sorted(
                    (
                        IngredientSourceDrug(item_seq=seq, item_name=seq_to_name[seq], qnt=qnt, unit=unit)
                        for seq, (qnt, unit) in seqs.items()
                    ),
                    key=lambda d: d.item_name,
                ),
                rules=rules_by_ingr.get(code, []),
            )
            for code, seqs in source_items_by_ingr.items()
        ]

        return IngredientScreeningResponse(ingredients=ingredients, unmatched_drug_names=unmatched)
