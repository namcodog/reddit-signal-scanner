import React from 'react';

type BadgeVariant = 'default' | 'secondary' | 'outline' | 'destructive';

type BadgeProps = React.HTMLAttributes<HTMLSpanElement> & {
  variant?: BadgeVariant;
};

const baseClass = [
  'inline-flex w-fit items-center justify-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium',
  'whitespace-nowrap shrink-0 transition-[color,box-shadow] [&>svg]:size-3 [&>svg]:pointer-events-none',
  'focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]',
].join(' ');

const variantClass: Record<BadgeVariant, string> = {
  default: 'border-transparent bg-primary text-primary-foreground hover:bg-primary/90',
  secondary: 'border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/90',
  outline: 'text-foreground hover:bg-accent hover:text-accent-foreground',
  destructive:
    'border-transparent bg-destructive text-white hover:bg-destructive/90 focus-visible:ring-destructive/20',
};

export const Badge: React.FC<BadgeProps> = ({ className = '', variant = 'default', children, ...rest }) => (
  <span data-slot="badge" className={[baseClass, variantClass[variant], className].filter(Boolean).join(' ')} {...rest}>
    {children}
  </span>
);

export default Badge;
