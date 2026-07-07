/**
 * T-LLM-1: 모든 LLM 응답에 항상 동반되는 면책 문구.
 * 절대 임의 삭제/숨김 금지 (TRD 성공요건과 직결) — FRONTEND_ARCHITECTURE.md 6번 참고.
 */
export default function DisclaimerBanner() {
  return <p role="note">이 정보는 의학적 조언이 아니며, 정확한 진단은 의료진과 상담하세요.</p>;
}
