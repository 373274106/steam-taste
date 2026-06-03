type Step = "library" | "taste" | "recs" | "regret" | "done";

const STEPS: { key: Step; label: string; detail: string }[] = [
  { key: "library", label: "拉取你的 Steam 游戏库", detail: "调用 GetOwnedGames API" },
  { key: "taste",   label: "计算 taste 向量",       detail: "playtime 加权 × TF-IDF 5000 款游戏标签" },
  { key: "recs",    label: "生成推荐",              detail: "余弦相似度 · 排除已拥有 · 质量过滤" },
  { key: "regret",  label: "检测 Library Regret",   detail: "HDBSCAN 聚类 · 纯/混合 regret 分类" },
];

export default function LoadingState({ step }: { step: Step }) {
  const currentIdx = STEPS.findIndex((s) => s.key === step);

  return (
    <div className="min-h-full flex items-center justify-center px-6 py-16">
      <div className="max-w-lg w-full">
        <h2 className="text-2xl font-bold mb-2">正在分析...</h2>
        <p className="text-sm text-slate-400 mb-8">
          首次分析需 5-10 秒，下次访问同账号是缓存秒返。
        </p>

        <div className="space-y-3">
          {STEPS.map((s, i) => {
            const status =
              i < currentIdx ? "done" : i === currentIdx ? "active" : "pending";
            return (
              <div
                key={s.key}
                className={`flex items-start gap-3 p-3 rounded-lg border transition-colors ${
                  status === "active"
                    ? "border-blue-700 bg-blue-950/30"
                    : status === "done"
                    ? "border-slate-800 bg-slate-900/30 opacity-70"
                    : "border-slate-800/50 opacity-40"
                }`}
              >
                <div className="mt-0.5">
                  {status === "done" && (
                    <span className="text-green-400 text-lg leading-none">✓</span>
                  )}
                  {status === "active" && (
                    <span className="inline-block w-4 h-4 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                  )}
                  {status === "pending" && (
                    <span className="inline-block w-4 h-4 border-2 border-slate-700 rounded-full" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className={`font-medium text-sm ${status === "active" ? "text-white" : "text-slate-300"}`}>
                    {s.label}
                  </div>
                  <div className="text-xs text-slate-500 mt-0.5">{s.detail}</div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Progress bar */}
        <div className="mt-6 h-1 bg-slate-800 rounded overflow-hidden">
          <div
            className="h-full bg-[var(--color-steam-blue)] transition-all duration-500"
            style={{ width: `${((currentIdx + 1) / STEPS.length) * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
}
