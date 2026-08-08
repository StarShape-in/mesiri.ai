interface PageTitleProps {
  title: string;
  sub?: string;
  actions?: React.ReactNode;
}

export default function PageTitle({ title, sub, actions }: PageTitleProps) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 px-4 sm:px-6 py-4 shrink-0 bg-[#F5F5F7]">
      <div className="min-w-0">
        <h1 className="text-lg sm:text-xl font-bold text-[#111] leading-tight tracking-tight">{title}</h1>
        {sub && <p className="text-xs text-[#6E6E80] mt-0.5 font-medium">{sub}</p>}
      </div>
      {actions && <div className="flex items-center flex-wrap gap-2 sm:shrink-0">{actions}</div>}
    </div>
  );
}
