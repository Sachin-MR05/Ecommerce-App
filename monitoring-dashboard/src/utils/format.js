export function formatDuration(ms) {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export function formatAmount(amount, currency) {
  if (amount === null || amount === undefined) return "—";
  const value = amount / 100; // minor units, matches Razorpay convention used across this codebase
  try {
    return new Intl.NumberFormat("en-IN", { style: "currency", currency: currency || "INR" }).format(value);
  } catch {
    return `${value.toFixed(2)} ${currency || ""}`;
  }
}

export function formatTime(iso) {
  if (!iso) return "—";
  const date = new Date(iso);
  return date.toLocaleTimeString([], { hour12: false });
}

export function formatClock(iso) {
  if (!iso) return "—";
  const date = new Date(iso);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
}

export function timeAgo(iso) {
  if (!iso) return "—";
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

export const STATUS_BADGE_CLASS = {
  SUCCESS: "badge-success",
  FAILED: "badge-failed",
  PENDING: "badge-pending",
  PROCESSING: "badge-processing",
  CANCELLED: "badge-cancelled",
};
