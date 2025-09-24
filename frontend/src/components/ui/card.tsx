import React from 'react';

const merge = (...classes: Array<string | undefined>) => classes.filter(Boolean).join(' ');

export const Card: React.FC<React.ComponentProps<'div'>> = ({ className = '', ...props }) => (
  <div
    data-slot="card"
    className={merge('bg-card text-card-foreground flex flex-col gap-6 rounded-xl border py-6 shadow-sm', className)}
    {...props}
  />
);

export const CardHeader: React.FC<React.ComponentProps<'div'>> = ({ className = '', ...props }) => (
  <div
    data-slot="card-header"
    className={merge(
      '@container/card-header grid auto-rows-min grid-rows-[auto_auto] items-start gap-1.5 px-6 has-data-[slot=card-action]:grid-cols-[1fr_auto] [.border-b]:pb-6',
      className
    )}
    {...props}
  />
);

export const CardTitle: React.FC<React.ComponentProps<'div'>> = ({ className = '', ...props }) => (
  <div data-slot="card-title" className={merge('font-semibold leading-none', className)} {...props} />
);

export const CardDescription: React.FC<React.ComponentProps<'div'>> = ({ className = '', ...props }) => (
  <div data-slot="card-description" className={merge('text-sm text-muted-foreground', className)} {...props} />
);

export const CardAction: React.FC<React.ComponentProps<'div'>> = ({ className = '', ...props }) => (
  <div data-slot="card-action" className={merge('col-start-2 row-span-2 row-start-1 self-start justify-self-end', className)} {...props} />
);

export const CardContent: React.FC<React.ComponentProps<'div'>> = ({ className = '', ...props }) => (
  <div data-slot="card-content" className={merge('px-6', className)} {...props} />
);

export const CardFooter: React.FC<React.ComponentProps<'div'>> = ({ className = '', ...props }) => (
  <div data-slot="card-footer" className={merge('flex items-center px-6 [.border-t]:pt-6', className)} {...props} />
);

export default Card;
