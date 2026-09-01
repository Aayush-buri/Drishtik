import { DrishtikLogo } from '../../assets/DrishtikLogo';

interface TopBarProps {
  section: string;
  children?: React.ReactNode;
}

export function TopBar({ section, children }: TopBarProps) {
  return (
    <header className="h-13 bg-white border-b border-gray-200 px-5 flex items-center justify-between shrink-0">
      <div className="flex items-center gap-3">
        <DrishtikLogo size={24} className="text-indigo-600" />
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-900 tracking-tight">Drishtik</span>
          <span className="text-gray-300 text-sm font-light select-none">/</span>
          <span className="text-sm text-gray-500 font-medium">{section}</span>
        </div>
      </div>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </header>
  );
}
