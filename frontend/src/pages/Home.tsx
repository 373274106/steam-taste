import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../lib/api";

export default function Home() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const errorParam = params.get("error");

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(
    errorParam === "auth_failed" ? "Steam 登录验证失败，请重试或用 URL 模式" : null,
  );

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const r = await api.resolveProfile(input.trim());
      navigate(`/result?steamid=${r.steam_id}`);
    } catch (err: any) {
      setError(err.message || "解析失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-full flex flex-col items-center justify-center px-6 py-16">
      <div className="max-w-2xl w-full">
        <h1 className="text-4xl sm:text-5xl font-bold mb-3 tracking-tight stagger-1">
          Steam <span className="text-[var(--color-steam-blue)]">Taste</span> Lens
        </h1>
        <p className="text-slate-400 text-base sm:text-lg mb-12 stagger-2">
          看清你自己的游戏品味。揭示 Steam 不愿意告诉你的事。
        </p>

        {/* Primary: Steam OpenID */}
        <a
          href={api.steamLoginUrl()}
          className="stagger-3 block w-full text-center bg-[var(--color-steam-blue)] hover:bg-blue-500 transition py-3 px-6 rounded-lg text-white font-semibold mb-4"
        >
          通过 Steam 登录
        </a>

        <div className="stagger-4 flex items-center gap-3 my-6 text-slate-500 text-sm">
          <div className="h-px bg-slate-700 flex-1" />
          <span>或</span>
          <div className="h-px bg-slate-700 flex-1" />
        </div>

        {/* Secondary: paste URL / SteamID / vanity */}
        <form onSubmit={handleSubmit} className="stagger-4 mb-4">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="贴 Steam profile URL / SteamID64 / vanity 名"
            className="w-full bg-slate-900 border border-slate-700 focus:border-slate-500 rounded-lg px-4 py-3 mb-3 outline-none"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="w-full bg-slate-700 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed transition py-3 px-6 rounded-lg font-medium"
          >
            {loading ? "解析中..." : "分析"}
          </button>
        </form>

        {/* Tertiary: demo card */}
        <button
          onClick={() => navigate("/result?steamid=-1&demo=1")}
          className="w-full mt-2 p-4 bg-slate-900/60 hover:bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-lg text-left transition group"
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-600 to-purple-700 flex items-center justify-center text-lg flex-shrink-0">
              🎮
            </div>
            <div className="flex-1">
              <div className="font-medium group-hover:text-white">
                先试试 Demo 模式
              </div>
              <div className="text-xs text-slate-500">
                预设玩家库（26 款 · Roguelite + 大策略 + 一些后悔购买），不需要 Steam 账号
              </div>
            </div>
            <span className="text-slate-500 group-hover:text-slate-300 transition">→</span>
          </div>
        </button>

        {error && (
          <div className="mt-6 p-4 bg-red-950/50 border border-red-900 rounded-lg text-red-300 text-sm">
            {error}
          </div>
        )}

        <div className="mt-16 text-xs text-slate-500 leading-relaxed">
          <p className="mb-2">隐私提示：</p>
          <ul className="list-disc list-inside space-y-1">
            <li>需要你的 Steam profile + game details 设为 Public</li>
            <li>我们不存储你的库数据，每次现场拉取</li>
            <li>Steam API key 只在后端，不会出现在前端代码</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
