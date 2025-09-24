export type ToastType = 'success' | 'error';

const TOAST_LIFETIME = 3200;
let container: HTMLDivElement | null = null;

function ensureContainer(): HTMLDivElement {
  if (container && document.body.contains(container)) {
    return container;
  }
  container = document.createElement('div');
  container.style.position = 'fixed';
  container.style.top = '20px';
  container.style.right = '20px';
  container.style.zIndex = '9999';
  container.style.display = 'flex';
  container.style.flexDirection = 'column';
  container.style.gap = '12px';
  document.body.appendChild(container);
  return container;
}

export function showToast(
  message: string,
  type: ToastType = 'success',
  duration = TOAST_LIFETIME,
): void {
  const root = ensureContainer();
  const toast = document.createElement('div');
  toast.textContent = message;
  toast.style.padding = '12px 16px';
  toast.style.borderRadius = '6px';
  toast.style.minWidth = '220px';
  toast.style.color = '#fff';
  toast.style.fontSize = '14px';
  toast.style.boxShadow = '0 8px 24px rgba(0,0,0,0.18)';
  toast.style.opacity = '0';
  toast.style.transform = 'translateY(-8px)';
  toast.style.transition = 'opacity 160ms ease, transform 160ms ease';
  toast.style.backgroundColor = type === 'success' ? '#16a34a' : '#dc2626';

  root.appendChild(toast);
  requestAnimationFrame(() => {
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';
  });

  window.setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(-8px)';
    toast.addEventListener(
      'transitionend',
      () => {
        toast.remove();
        if (container && container.childElementCount === 0) {
          container.remove();
          container = null;
        }
      },
      { once: true },
    );
  }, duration);
}
