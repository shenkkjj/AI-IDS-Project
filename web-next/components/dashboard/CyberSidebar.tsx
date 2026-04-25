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
    <aside className="w-full md:w-64 bg-cyber-bg border-b md:border-b-0 md:border-r border-cyber-cyan/30 p-4 flex flex-col">
      <div className="mb-8 hidden md:block">
        <h2 className="text-xl font-bold text-cyber-cyan uppercase tracking-widest shadow-neon-cyan inline-block p-2 border border-cyber-cyan/50">
          Nexus<span className="text-cyber-orange">OS</span>
        </h2>
        <div className="text-xs text-cyber-text/50 mt-2">v.9.0.4 [SECURE]</div>
      </div>

      <nav className="flex md:flex-col gap-2 overflow-x-auto md:overflow-visible pb-2 md:pb-0">
        {items.map((item) => (
          <button
            key={item.key}
            type="button"
            onClick={() => onSelect(item.key)}
            className={`flex items-center gap-3 p-3 text-left transition-all duration-200 border-l-2 whitespace-nowrap md:whitespace-normal ${
              active === item.key
                ? "border-cyber-cyan bg-cyber-cyan/10 text-cyber-cyan shadow-[inset_4px_0_0_rgba(0,245,255,0.8)]"
                : "border-transparent text-cyber-text/70 hover:bg-white/5 hover:text-cyber-text"
            }`}
          >
            <span className="font-bold text-lg w-6 text-center opacity-70">[{item.icon}]</span>
            <span className="uppercase text-sm tracking-wider">{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="mt-auto hidden md:block pt-8 border-t border-cyber-cyan/20">
        <div className="text-xs text-cyber-text/40 mb-2">SYSTEM STATUS</div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-green-500 text-sm tracking-widest">ONLINE</span>
        </div>
      </div>
    </aside>
  );
}
