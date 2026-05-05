"use client";

type RouteKey = "overview" | "monitor" | "waf" | "ai" | "report";

type NavItem = {
  key: RouteKey;
  label: string;
  icon: string;
};

type CyberSidebarProps = {
  items: NavItem[];
  active: RouteKey;
  onSelect: (key: RouteKey) => void;
};

export default function CyberSidebar({ items, active, onSelect }: CyberSidebarProps) {
  return (
    <aside className="w-full md:w-56 bg-[#0F172A] border-b md:border-b-0 md:border-r border-slate-700/50 p-5 flex flex-col">
      <div className="mb-8 hidden md:block">
        <h2 className="text-lg font-bold text-cyber-cyan uppercase tracking-widest inline-block p-2 border border-cyber-cyan/40">
          Nexus<span className="text-cyber-orange">OS</span>
        </h2>
        <div className="text-xs text-slate-500 mt-2">v.9.0.4 [SECURE]</div>
      </div>

      <nav className="flex md:flex-col gap-1 overflow-x-auto md:overflow-visible pb-2 md:pb-0">
        {items.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => onSelect(item.key)}
            className={`flex items-center gap-3 px-3 py-2.5 text-left transition-all duration-200 rounded-md whitespace-nowrap md:whitespace-normal ${
              active === item.key
                ? "bg-cyber-cyan/10 text-cyber-cyan border-l-2 border-cyber-cyan"
                : "border-l-2 border-transparent text-slate-400 hover:bg-white/[0.03] hover:text-slate-200"
            }`}
          >
            <span className="font-bold text-base w-5 text-center opacity-60">{item.icon}</span>
            <span className="uppercase text-sm tracking-wider">{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="mt-auto hidden md:block pt-8 border-t border-slate-700/30">
        <div className="text-xs text-slate-600 mb-2">SYSTEM STATUS</div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-emerald-500 text-sm tracking-widest">ONLINE</span>
        </div>
      </div>
    </aside>
  );
}
