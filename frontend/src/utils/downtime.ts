/**
 * Parse a human-readable downtime string to seconds.
 * 
 * Accepts formats like: "1h", "30m", "45s", "1h 30m", "2h 15m 30s"
 * 
 * @param downtimeStr - Human-readable downtime string
 * @returns Total seconds as number
 * @throws Error if format is invalid
 */
export function parseDowntimeString(downtimeStr: string): number {
  if (!downtimeStr || !downtimeStr.trim()) {
    throw new Error('Downtime string cannot be empty');
  }

  // Remove extra whitespace
  const trimmed = downtimeStr.trim();

  // Pattern to match time components: number followed by h/m/s
  const pattern = /(\d+)\s*([hms])/gi;
  const matches = [...trimmed.matchAll(pattern)];

  if (matches.length === 0) {
    throw new Error(
      "Invalid downtime format. Use formats like '1h', '30m', '1h 30m', or '2h 15m 30s'"
    );
  }

  let totalSeconds = 0;
  const seenUnits = new Set<string>();

  for (const match of matches) {
    const value = parseInt(match[1], 10);
    const unit = match[2].toLowerCase();

    // Check for duplicate units
    if (seenUnits.has(unit)) {
      throw new Error(`Duplicate time unit '${unit}' in downtime string`);
    }
    seenUnits.add(unit);

    if (unit === 'h') {
      totalSeconds += value * 3600;
    } else if (unit === 'm') {
      totalSeconds += value * 60;
    } else if (unit === 's') {
      totalSeconds += value;
    }
  }

  if (totalSeconds < 0) {
    throw new Error('Downtime cannot be negative');
  }

  return totalSeconds;
}

/**
 * Format seconds to human-readable downtime string.
 * 
 * @param seconds - Total seconds (can be null)
 * @returns Human-readable string like "1h 30m" or null if input is null
 */
export function formatDowntimeSeconds(seconds: number | null): string | null {
  if (seconds === null || seconds === undefined) {
    return null;
  }

  if (seconds === 0) {
    return '0s';
  }

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  const parts: string[] = [];
  if (hours > 0) {
    parts.push(`${hours}h`);
  }
  if (minutes > 0) {
    parts.push(`${minutes}m`);
  }
  if (secs > 0) {
    parts.push(`${secs}s`);
  }

  return parts.join(' ');
}

/**
 * Validate a downtime string without throwing errors.
 * 
 * @param downtimeStr - Human-readable downtime string
 * @returns true if valid, false otherwise
 */
export function isValidDowntimeString(downtimeStr: string): boolean {
  try {
    parseDowntimeString(downtimeStr);
    return true;
  } catch {
    return false;
  }
}
