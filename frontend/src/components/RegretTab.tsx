import { useState } from "react";
import type { RegretCluster, RegretReport } from "../lib/types";

type Kind = "mixed" | "pure" | "sleeping";

export default function RegretTab({ regret }: { regret: RegretReport }) {
  const [kind, setKind] = useState<Kind>("mixed");

  return (
    <div>
      {/* Stats banner */}
      <div className="mb-6 grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Library" value={regret.stats.total_games.toLocaleString()} />
        <Stat label="In corpus" value={regret.stats.in_corpus.toLocaleString()} />
        <Stat label="Untouched" value={regret.stats.sleeping_count.toLocaleString()} suffix=" games" accent="red" />
        <Stat label="Regret patterns" value={regret.stats.regret_cluster_count.toLocaleString()} accent="amber" />
      </div>

      <div className="flex gap-2 mb-6 border-b border-slate-800">
        <KindButton active={kind === "mixed"} onClick={() => setKind("mixed")}>
          🩸 Mixed Regret ({regret.stats.mixed_count})
        </KindButton>
        <KindButton active={kind === "pure"} onClick={() => setKind("pure")}>
          💀 Pure Regret ({regret.stats.pure_count})
        </KindButton>
        <KindButton active={kind === "sleeping"} onClick={() => setKind("sleeping")}>
          💤 Sleeping Games ({regret.stats.sleeping_count})
        </KindButton>
      </div>

      {kind === "mixed" && (
        <>
          <Intro>
            你<strong>找到了真爱</strong>，但还是忍不住买同类。下面这些类型里你已经有了代表作，
            <strong>再买同类的基本不会玩</strong>。
          </Intro>
          <ClusterList clusters={regret.mixed.slice(0, 10)} kind="mixed" />
        </>
      )}

      {kind === "pure" && (
        <>
          <Intro>
            你<strong>反复尝试</strong>但从来没真正入坑的类型。每次打折都觉得"这次会爱的"，
            然后还是没玩。<strong>这些类型不适合你</strong>。
          </Intro>
          <ClusterList clusters={regret.pure.slice(0, 10)} kind="pure" />
        </>
      )}

      {kind === "sleeping" && (
        <>
          <Intro>
            买了但<strong>不到 30 分钟</strong>的游戏。展示前 30 款，按 playtime 升序。
          </Intro>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {regret.sleeping_preview.map((g) => (
              <a
                key={g.appid}
                href={`https://store.steampowered.com/app/${g.appid}`}
                target="_blank"
                rel="noopener noreferrer"
                className="bg-[var(--color-steam-panel)] border border-slate-800 hover:border-slate-700 rounded p-3 transition"
              >
                <img
                  src={`https://cdn.akamai.steamstatic.com/steam/apps/${g.appid}/header.jpg`}
                  alt=""
                  className="w-full aspect-[460/215] object-cover rounded mb-2 bg-slate-900"
                  onError={(e) => ((e.target as HTMLImageElement).style.display = "none")}
                />
                <div className="text-sm font-medium truncate">{g.name}</div>
                <div className="text-xs text-slate-500">{g.playtime_min} min</div>
              </a>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  suffix,
  accent,
}: {
  label: string;
  value: string;
  suffix?: string;
  accent?: "red" | "amber";
}) {
  const color =
    accent === "red" ? "text-red-300" : accent === "amber" ? "text-amber-300" : "text-slate-100";
  return (
    <div className="bg-[var(--color-steam-panel)] border border-slate-800 rounded p-3">
      <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">{label}</div>
      <div className={`text-2xl font-bold ${color}`}>
        {value}
        {suffix && <span className="text-sm font-normal text-slate-500">{suffix}</span>}
      </div>
    </div>
  );
}

function KindButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 -mb-px border-b-2 transition text-sm ${
        active
          ? "border-[var(--color-steam-blue)] text-white"
          : "border-transparent text-slate-400 hover:text-slate-200"
      }`}
    >
      {children}
    </button>
  );
}

function Intro({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-6 p-4 bg-slate-900/40 border border-slate-800 rounded-lg text-sm text-slate-300">
      {children}
    </div>
  );
}

function ClusterList({ clusters, kind }: { clusters: RegretCluster[]; kind: "mixed" | "pure" }) {
  if (clusters.length === 0) {
    return <div className="text-slate-500 text-center py-12">没有此类簇</div>;
  }
  const accent = kind === "mixed" ? "border-amber-900/50 bg-amber-950/10" : "border-red-900/50 bg-red-950/10";

  return (
    <div className="space-y-4">
      {clusters.map((c, i) => (
        <div key={c.label} className={`border rounded-lg p-5 ${accent}`}>
          <div className="flex items-start justify-between gap-4 mb-3">
            <div>
              <div className="text-xs text-slate-500 mb-1">#{i + 1}</div>
              <h3 className="text-lg font-semibold">
                {c.dominant_tags.slice(0, 3).join(" / ") || `Cluster ${c.label}`}
              </h3>
            </div>
            <div className="text-right text-xs text-slate-400">
              <div>{c.game_count} games</div>
              <div>median {c.median_hours}h</div>
            </div>
          </div>
          <div className="text-sm text-slate-200 whitespace-pre-line mb-4 leading-relaxed">
            {c.diagnosis}
          </div>

          {/* Game thumbnails */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
            {c.games.slice(0, 5).map((g) => (
              <a
                key={g.appid}
                href={`https://store.steampowered.com/app/${g.appid}`}
                target="_blank"
                rel="noopener noreferrer"
                className="block"
              >
                <img
                  src={`https://cdn.akamai.steamstatic.com/steam/apps/${g.appid}/header.jpg`}
                  alt={g.name}
                  className="w-full aspect-[460/215] object-cover rounded bg-slate-900"
                  onError={(e) => ((e.target as HTMLImageElement).style.display = "none")}
                />
                <div className="text-xs mt-1 truncate">{g.name}</div>
                <div className="text-xs text-slate-500">{g.playtime_hours}h</div>
              </a>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
