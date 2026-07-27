// item_seq가 "AUTO_"로 시작하면 마스터 DB 매칭/공공API 조회 모두 실패해 임시로 생성된
// 약이라는 뜻이다 - 이런 약은 병용금기(DUR) 체크에서 제외되므로(app/services/medication_service.py
// check_interactions) 사용자에게 그 사실을 알려야 한다.
export function isUnverifiedDrug(itemSeq: string): boolean {
  return itemSeq.startsWith("AUTO_");
}
