import teamLogo from "../assets/lc-logo.png";
export function ShieldMark({ className = "h-9 w-9" }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <path d="M32 4 8 13v17c0 15 10 26 24 30 14-4 24-15 24-30V13Z" fill="#0b2047" />
      <path d="M32 10 14 17v13c0 11 7 20 18 24 11-4 18-13 18-24V17Z" fill="#12b09a" />
      <path d="m22 32 7 7 14-15" fill="none" stroke="#fff" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Logo({ light = false, subtitle = true }: { light?: boolean; subtitle?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <ShieldMark />
      <div className="leading-tight">
        <div className={`text-lg font-extrabold tracking-tight ${light ? "text-white" : "text-navy-900"}`}>
          Suraksha<span className="text-teal-400">FD</span>
        </div>
        {subtitle && (
          <div className={`text-[10px] font-medium uppercase tracking-[0.14em] ${light ? "text-navy-200" : "text-slate-500"}`}>
            FDR &amp; Deposit Portal
          </div>
        )}
      </div>
    </div>
  );
}

/** Team Lynxcode logo. On dark backgrounds it sits on a white badge so the black "Lynx" stays legible. */
export function TeamLogo({ badge = false, className = "h-5" }: { badge?: boolean; className?: string }) {
  const img = <img src={teamLogo} alt="Team LynxCode" className={`${className} w-auto`} />;
  return badge ? <span className="inline-flex items-center rounded-md bg-white px-2.5 py-1.5 shadow-sm">{img}</span> : img;
}
