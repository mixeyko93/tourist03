import type { ReactNode } from "react";

type SectionHeadingProps = {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
};

export function SectionHeading({ eyebrow, title, description, actions }: SectionHeadingProps) {
  return (
    <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div className="space-y-2">
        {eyebrow ? (
          <span className="inline-flex rounded-full border border-[#2F80ED]/25 bg-card/70 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-[#2F80ED] shadow-sm">
            {eyebrow}
          </span>
        ) : null}
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold tracking-[-0.04em] text-foreground md:text-3xl">{title}</h1>
          {description ? <p className="max-w-2xl text-sm text-muted-foreground md:text-[15px]">{description}</p> : null}
        </div>
      </div>
      {actions ? <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row sm:flex-wrap sm:items-center">{actions}</div> : null}
    </div>
  );
}
