import React, { createContext, useContext, useMemo, useState, ReactNode } from 'react';

const merge = (...classes: Array<string | undefined>) => classes.filter(Boolean).join(' ');

type TabsContextType = {
  value: string;
  setValue: (v: string) => void;
};

const TabsContext = createContext<TabsContextType | null>(null);

export interface TabsProps {
  value?: string;
  defaultValue?: string;
  onValueChange?: (v: string) => void;
  className?: string;
  children: ReactNode;
}

export const Tabs: React.FC<TabsProps> = ({ value, defaultValue, onValueChange, className = '', children }) => {
  const [internal, setInternal] = useState<string>(defaultValue ?? 'overview');
  const active = value ?? internal;
  const setValue = (v: string) => {
    if (onValueChange) onValueChange(v);
    if (value === undefined) setInternal(v);
  };
  const ctx = useMemo(() => ({ value: active, setValue }), [active]);
  return (
    <TabsContext.Provider value={ctx}>
      <div data-slot="tabs" className={merge('flex flex-col gap-2', className)}>
        {children}
      </div>
    </TabsContext.Provider>
  );
};

export const TabsList: React.FC<React.ComponentProps<'div'>> = ({ className = '', ...rest }) => (
  <div
    data-slot="tabs-list"
    className={merge('bg-muted text-muted-foreground inline-flex h-9 w-fit items-center justify-center rounded-lg p-[3px]', className)}
    {...rest}
  />
);

export interface TabsTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  value: string;
}

export const TabsTrigger: React.FC<TabsTriggerProps> = ({ value, className = '', children, ...rest }) => {
  const ctx = useContext(TabsContext);
  if (!ctx) throw new Error('TabsTrigger must be used within Tabs');
  const active = ctx.value === value;
  return (
    <button
      type="button"
      onClick={() => ctx.setValue(value)}
      data-state={active ? 'active' : 'inactive'}
      className={merge(
        "inline-flex h-[calc(100%-1px)] flex-1 items-center justify-center gap-1.5 rounded-md border border-transparent px-2 py-1 text-sm font-medium whitespace-nowrap transition-[color,box-shadow] focus-visible:ring-[3px] focus-visible:outline-1 focus-visible:border-ring focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
        active ? 'bg-background text-foreground shadow-sm' : 'text-foreground hover:bg-accent hover:text-accent-foreground',
        className
      )}
      aria-selected={active}
      {...rest}
    >
      {children}
    </button>
  );
};

export interface TabsContentProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string;
}

export const TabsContent: React.FC<TabsContentProps> = ({ value, className = '', children, ...rest }) => {
  const ctx = useContext(TabsContext);
  if (!ctx) throw new Error('TabsContent must be used within Tabs');
  if (ctx.value !== value) return null;
  return (
    <div data-slot="tabs-content" className={merge('flex-1 outline-none', className)} {...rest}>
      {children}
    </div>
  );
};

export default Tabs;
