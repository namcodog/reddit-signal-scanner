import React from 'react';

export interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value?: number;
  max?: number;
  indicatorClassName?: string;
}

export const Progress: React.FC<ProgressProps> = ({ value = 0, max = 100, className = '', indicatorClassName = '', ...rest }) => {
  const safeMax = Number.isFinite(max) && max > 0 ? max : 100;
  const clamped = Math.min(Math.max(value, 0), safeMax);
  const percentage = (clamped / safeMax) * 100;

  return (
    <div
      data-slot="progress"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={safeMax}
      aria-valuenow={clamped}
      className={`bg-primary/20 relative h-2 w-full overflow-hidden rounded-full ${className}`}
      {...rest}
    >
      <div
        data-slot="progress-indicator"
        className={`bg-primary absolute inset-y-0 left-0 h-full w-full transition-all ${indicatorClassName}`}
        style={{ transform: `translateX(-${100 - percentage}%)` }}
      />
    </div>
  );
};

export default Progress;
