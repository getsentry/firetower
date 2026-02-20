import {describe, expect, test} from 'bun:test';

import {
  formatDowntimeSeconds,
  isValidDowntimeString,
  parseDowntimeString,
} from './downtime';

describe('parseDowntimeString', () => {
  test('parses hours only', () => {
    expect(parseDowntimeString('1h')).toBe(3600);
    expect(parseDowntimeString('2h')).toBe(7200);
    expect(parseDowntimeString('24h')).toBe(86400);
  });

  test('parses minutes only', () => {
    expect(parseDowntimeString('1m')).toBe(60);
    expect(parseDowntimeString('30m')).toBe(1800);
    expect(parseDowntimeString('45m')).toBe(2700);
  });

  test('parses seconds only', () => {
    expect(parseDowntimeString('1s')).toBe(1);
    expect(parseDowntimeString('30s')).toBe(30);
    expect(parseDowntimeString('45s')).toBe(45);
  });

  test('parses combined hours and minutes', () => {
    expect(parseDowntimeString('1h 30m')).toBe(5400);
    expect(parseDowntimeString('2h 15m')).toBe(8100);
  });

  test('parses combined hours, minutes, and seconds', () => {
    expect(parseDowntimeString('1h 30m 45s')).toBe(5445);
    expect(parseDowntimeString('2h 15m 30s')).toBe(8130);
  });

  test('parses with extra whitespace', () => {
    expect(parseDowntimeString('  1h  30m  ')).toBe(5400);
    expect(parseDowntimeString('1h30m')).toBe(5400);
  });

  test('is case insensitive', () => {
    expect(parseDowntimeString('1H')).toBe(3600);
    expect(parseDowntimeString('30M')).toBe(1800);
    expect(parseDowntimeString('45S')).toBe(45);
    expect(parseDowntimeString('1H 30M 45S')).toBe(5445);
  });

  test('throws error for empty string', () => {
    expect(() => parseDowntimeString('')).toThrow('Downtime string cannot be empty');
    expect(() => parseDowntimeString('   ')).toThrow('Downtime string cannot be empty');
  });

  test('throws error for invalid format', () => {
    expect(() => parseDowntimeString('invalid')).toThrow('Invalid downtime format');
    expect(() => parseDowntimeString('123')).toThrow('Invalid downtime format');
    expect(() => parseDowntimeString('abc def')).toThrow('Invalid downtime format');
  });

  test('throws error for duplicate units', () => {
    expect(() => parseDowntimeString('1h 2h')).toThrow("Duplicate time unit 'h'");
    expect(() => parseDowntimeString('30m 15m')).toThrow("Duplicate time unit 'm'");
    expect(() => parseDowntimeString('10s 20s')).toThrow("Duplicate time unit 's'");
  });
});

describe('formatDowntimeSeconds', () => {
  test('formats hours only', () => {
    expect(formatDowntimeSeconds(3600)).toBe('1h');
    expect(formatDowntimeSeconds(7200)).toBe('2h');
    expect(formatDowntimeSeconds(86400)).toBe('24h');
  });

  test('formats minutes only', () => {
    expect(formatDowntimeSeconds(60)).toBe('1m');
    expect(formatDowntimeSeconds(1800)).toBe('30m');
    expect(formatDowntimeSeconds(2700)).toBe('45m');
  });

  test('formats seconds only', () => {
    expect(formatDowntimeSeconds(1)).toBe('1s');
    expect(formatDowntimeSeconds(30)).toBe('30s');
    expect(formatDowntimeSeconds(45)).toBe('45s');
  });

  test('formats combined hours and minutes', () => {
    expect(formatDowntimeSeconds(5400)).toBe('1h 30m');
    expect(formatDowntimeSeconds(8100)).toBe('2h 15m');
  });

  test('formats combined hours, minutes, and seconds', () => {
    expect(formatDowntimeSeconds(5445)).toBe('1h 30m 45s');
    expect(formatDowntimeSeconds(8130)).toBe('2h 15m 30s');
  });

  test('formats zero seconds', () => {
    expect(formatDowntimeSeconds(0)).toBe('0s');
  });

  test('returns null for null input', () => {
    expect(formatDowntimeSeconds(null)).toBe(null);
  });
});

describe('isValidDowntimeString', () => {
  test('returns true for valid formats', () => {
    expect(isValidDowntimeString('1h')).toBe(true);
    expect(isValidDowntimeString('30m')).toBe(true);
    expect(isValidDowntimeString('45s')).toBe(true);
    expect(isValidDowntimeString('1h 30m')).toBe(true);
    expect(isValidDowntimeString('2h 15m 30s')).toBe(true);
  });

  test('returns false for invalid formats', () => {
    expect(isValidDowntimeString('')).toBe(false);
    expect(isValidDowntimeString('invalid')).toBe(false);
    expect(isValidDowntimeString('123')).toBe(false);
    expect(isValidDowntimeString('1h 2h')).toBe(false);
  });
});

describe('parseDowntimeString and formatDowntimeSeconds roundtrip', () => {
  test('roundtrip conversion works correctly', () => {
    const testCases = ['1h', '30m', '45s', '1h 30m', '2h 15m 30s'];

    for (const input of testCases) {
      const seconds = parseDowntimeString(input);
      const formatted = formatDowntimeSeconds(seconds);
      const reparsed = parseDowntimeString(formatted!);
      expect(reparsed).toBe(seconds);
    }
  });
});
