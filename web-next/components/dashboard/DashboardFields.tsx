"use client";

export function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <label className="block text-[10px] font-mono uppercase tracking-[0.15em] text-ink-tertiary mb-1.5">
      {children}
    </label>
  );
}

export function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className="w-full bg-transparent text-ink text-sm py-2 px-0 border-0 border-b border-line focus:outline-none focus:border-accent transition-colors placeholder:text-ink-tertiary"
    />
  );
}

export function SelectInput(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className="w-full bg-transparent text-ink text-sm py-2 px-0 border-0 border-b border-line focus:outline-none focus:border-accent transition-colors cursor-pointer"
    />
  );
}
