export const DISCLAIMER_TEXT = "本站資訊僅供參考，不能取代醫生或營養師意見。";

export default function Disclaimer() {
  return (
    <p className="border-t border-line pt-4 text-xs leading-relaxed text-ink-muted">
      {DISCLAIMER_TEXT}濕疹誘因因人而異，嚴重或持續不適請諮詢醫生或註冊營養師。
      本站不建議在未確診食物過敏的情況下盲目戒口。
    </p>
  );
}
