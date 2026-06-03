import { Link } from "react-router-dom";

interface Props {
  message: string;
}

interface Diagnosis {
  title: string;
  body: React.ReactNode;
  cta?: { label: string; href: string };
}

function diagnose(message: string): Diagnosis {
  const m = message.toLowerCase();

  // Private profile (most common — backend returns 403 with helpful detail)
  if (m.includes("private") || m.includes("no library data") || m.includes("profile may be private")) {
    return {
      title: "🔒 资料没公开",
      body: (
        <>
          <p>Steam 默认不公开你的游戏库。我们没法分析你看不见的东西。</p>
          <p className="mt-3">两个设置都要打开：</p>
          <ul className="list-disc list-inside text-slate-300 mt-2 space-y-1">
            <li><strong>My profile</strong> → Public</li>
            <li><strong>Game details</strong> → Public（这条单独设置，最容易漏）</li>
          </ul>
        </>
      ),
      cta: { label: "去 Steam 隐私设置", href: "https://steamcommunity.com/my/edit/settings" },
    };
  }

  // Vanity / SteamID not found
  if (m.includes("vanity") || m.includes("not found") || m.includes("cannot interpret")) {
    return {
      title: "🔍 找不到这个用户",
      body: (
        <>
          <p>输入的 SteamID / URL / vanity 名解析不出来。常见原因：</p>
          <ul className="list-disc list-inside text-slate-300 mt-2 space-y-1">
            <li>vanity 名拼错</li>
            <li>账号已被删除或临时锁定</li>
            <li>不是有效的 17 位 SteamID64</li>
          </ul>
        </>
      ),
    };
  }

  // Network / 5xx — backend or Steam API down
  if (m.includes("network") || m.includes("503") || m.includes("502") || m.includes("timeout") || m.includes("fetch")) {
    return {
      title: "📡 服务暂时不通",
      body: (
        <>
          <p>后端或 Steam API 没响应。可能：</p>
          <ul className="list-disc list-inside text-slate-300 mt-2 space-y-1">
            <li>后端服务挂了 / 还没启动</li>
            <li>Steam Web API 限流（每天 100k 调用限额，几乎不会爆）</li>
            <li>你的网络访问不到 steampowered.com</li>
          </ul>
          <p className="mt-3 text-xs text-slate-500">技术细节: <code>{message}</code></p>
        </>
      ),
    };
  }

  // Fallback
  return {
    title: "⚠ 出错了",
    body: (
      <>
        <p>未预期的错误。把这条贴给我可能能帮到诊断：</p>
        <pre className="mt-3 p-3 bg-slate-900 rounded text-xs text-slate-300 whitespace-pre-wrap overflow-x-auto">
          {message}
        </pre>
      </>
    ),
  };
}

export default function ErrorState({ message }: Props) {
  const d = diagnose(message);

  return (
    <div className="min-h-full flex items-center justify-center px-6 py-16">
      <div className="max-w-xl w-full">
        <h2 className="text-2xl font-bold mb-4">{d.title}</h2>
        <div className="text-slate-400 leading-relaxed">{d.body}</div>

        <div className="flex gap-3 mt-8">
          <Link
            to="/"
            className="bg-slate-800 hover:bg-slate-700 transition px-4 py-2 rounded font-medium"
          >
            ← 返回主页
          </Link>
          {d.cta && (
            <a
              href={d.cta.href}
              target="_blank"
              rel="noopener noreferrer"
              className="bg-[var(--color-steam-blue)] hover:bg-blue-500 transition px-4 py-2 rounded font-medium"
            >
              {d.cta.label} →
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
