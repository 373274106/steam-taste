import { useState } from "react";
import type { RecCard, RecommendResponse } from "../lib/types";

interface Props {
  recsNew: RecommendResponse;
  recsOwned: RecommendResponse;
}

type Mode = "new" | "owned";

export default function RecommendationsTab({ recsNew, recsOwned }: Props) {
  const [mode, setMode] = useState<Mode>("new");
  const items = mode === "new" ? recsNew.items : recsOwned.items;

  return (
    <div>
      <div className="flex gap-2 mb-6 border-b border-slate-800">
        <ModeButton active={mode === "new"} onClick={() => setMode("new")}>
          💎 Discover New
        </ModeButton>
        <ModeButton active={mode === "owned"} onClick={() => setMode("owned")}>
          🎯 Play What You Own
        </ModeButton>
      </div>

      <div className="mb-4 text-sm text-slate-400">
        {mode === "new" ? (
          <>
            根据你的 taste 推荐你<strong className="text-slate-200">还没买</strong>的游戏。
            Steam 不会做的事：解释为什么推。
          </>
        ) : (
          <>
            你<strong className="text-slate-200">已经买了但几乎没玩</strong>的游戏，
            按 taste 契合度排——别再买新的了，先玩完你已有的。
          </>
        )}
      </div>

      <div className="space-y-4">
        {items.length === 0 ? (
          <div className="text-slate-500 text-center py-12">
            {mode === "owned" ? "你库里没有未玩的契合游戏——很好的购物纪律。" : "没有推荐结果"}
          </div>
        ) : (
          items.map((card) => <RecCardView key={card.appid} card={card} mode={mode} />)
        )}
      </div>
    </div>
  );
}

function ModeButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
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

function RecCardView({ card, mode }: { card: RecCard; mode: Mode }) {
  return (
    <div className="flex gap-4 bg-[var(--color-steam-panel)] border border-slate-800 rounded-lg overflow-hidden hover:border-slate-700 transition">
      {card.header_image ? (
        <img
          src={card.header_image}
          alt={card.name}
          className="w-48 h-auto object-cover bg-slate-900 flex-shrink-0"
          onError={(e) => ((e.target as HTMLImageElement).style.display = "none")}
        />
      ) : (
        <div className="w-48 bg-slate-900 flex-shrink-0" />
      )}

      <div className="flex-1 p-4 min-w-0">
        <div className="flex items-start justify-between gap-3 mb-2">
          <h3 className="text-lg font-semibold truncate">{card.name}</h3>
          <div className="text-right flex-shrink-0">
            <div className="text-xl font-bold text-[var(--color-steam-blue)]">
              {card.match_pct.toFixed(0)}%
            </div>
            <div className="text-xs text-slate-500">match</div>
          </div>
        </div>

        {mode === "owned" && card.current_playtime_min !== undefined && (
          <div className="text-xs text-amber-400 mb-2">
            你已经买了 · 玩过 {card.current_playtime_min} 分钟
          </div>
        )}

        {card.shared_tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-3">
            {card.shared_tags.slice(0, 5).map((t) => (
              <span
                key={t}
                className="text-xs px-2 py-0.5 bg-blue-950/50 border border-blue-900 rounded text-blue-300"
              >
                {t}
              </span>
            ))}
          </div>
        )}

        {card.evidence_games.length > 0 && (
          <div className="text-sm text-slate-400">
            <span className="text-slate-500">因为你玩过</span>{" "}
            {card.evidence_games.map((g, i) => (
              <span key={g.appid}>
                <strong className="text-slate-300">{g.name}</strong>{" "}
                <span className="text-slate-500">({g.playtime_hours}h)</span>
                {i < card.evidence_games.length - 1 && "  ·  "}
              </span>
            ))}
          </div>
        )}

        <div className="mt-3">
          <a
            href={card.steam_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-blue-400 hover:text-blue-300"
          >
            在 Steam 上查看 →
          </a>
        </div>
      </div>
    </div>
  );
}
