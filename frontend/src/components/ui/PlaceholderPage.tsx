// src/components/ui/PlaceholderPage.tsx
// 아직 화면이 없는 도메인의 자리표시자입니다.
// 이 컴포넌트를 참고하지 말고, features/schedule/SchedulePage.tsx 를 참고해서
// 실제 화면을 만들어주세요 (API 함수는 이미 src/api/endpoints/ 에 준비되어 있습니다).
interface Props {
  title: string;
  apiFile: string;
  note?: string;
}

export default function PlaceholderPage({ title, apiFile, note }: Props) {
  return (
    <div className="mx-auto max-w-2xl p-6">
      <h1 className="mb-2 text-2xl font-bold">{title}</h1>
      <div
        className="rounded-xl border border-dashed p-6"
        style={{ borderColor: "var(--panel-border)", color: "var(--text-secondary)" }}
      >
        <p className="mb-2">🚧 아직 화면이 만들어지지 않았습니다 (TODO).</p>
        <p className="mb-2 text-sm">
          API 함수는 <code className="rounded bg-black/30 px-1">{apiFile}</code> 에 이미 준비되어 있어요.
          <code className="rounded bg-black/30 px-1">features/schedule/</code> 폴더의 구현을 참고해서 화면만 만들면 됩니다.
        </p>
        {note && <p className="text-sm" style={{ color: "var(--accent-pink)" }}>{note}</p>}
      </div>
    </div>
  );
}
