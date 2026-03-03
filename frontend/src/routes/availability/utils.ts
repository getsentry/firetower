export type AvailabilityLevel = 'success' | 'warning' | 'danger';

export function getAvailabilityLevel(pct: number): AvailabilityLevel {
  if (pct >= 99.9) return 'success';
  if (pct >= 99.85) return 'warning';
  return 'danger';
}
