import {readFile, writeFile} from 'node:fs/promises';

import {baseTheme, darkTheme, lightTheme} from '@sentry/scraps/theme';
import {format} from 'prettier';

const colorGroups = ['background', 'border', 'content', 'graphics'];
const groups = {
  ...Object.fromEntries(colorGroups.map(group => [group, lightTheme.tokens[group]])),
  space: baseTheme.space,
  radius: baseTheme.radius,
  fontSize: baseTheme.font.size,
  fontWeight: {
    regular: baseTheme.font.weight.sans.regular,
    medium: baseTheme.font.weight.sans.medium,
  },
  fontFamily: baseTheme.font.family,
  lineHeight: baseTheme.font.lineHeight,
};

function leaves(values, path = []) {
  return Object.entries(values).flatMap(([key, value]) => {
    const next = [...path, key];
    if (value !== null && typeof value === 'object') return leaves(value, next);
    if (typeof value !== 'string' && typeof value !== 'number') {
      throw new Error(`Invalid Scraps token ${next.join('.')}`);
    }
    return [{path: next, value: String(value)}];
  });
}

function tokenKey(path) {
  return path
    .map((key, index) => (index === 0 ? key : key[0].toUpperCase() + key.slice(1)))
    .join('');
}

const inventory = Object.entries(groups).flatMap(([group, values]) => {
  const entries = leaves(values).map(({path, value}) => ({
    group,
    key: tokenKey(path),
    value,
  }));
  if (new Set(entries.map(entry => entry.key)).size !== entries.length) {
    throw new Error(`Duplicate StyleX token in ${group}`);
  }
  return entries;
});
const darkEntries = colorGroups.flatMap(group =>
  leaves(darkTheme.tokens[group]).map(({path, value}) => [
    `${group}.${tokenKey(path)}`,
    value,
  ])
);
const lightPaths = inventory
  .filter(entry => colorGroups.includes(entry.group))
  .map(entry => `${entry.group}.${entry.key}`)
  .sort();
if (
  JSON.stringify(lightPaths) !== JSON.stringify(darkEntries.map(([key]) => key).sort())
) {
  throw new Error('Scraps light and dark token paths differ');
}
const darkValues = new Map(darkEntries);

const typescript = [
  "import * as stylex from '@stylexjs/stylex';",
  ...Object.keys(groups).map(group =>
    [
      `export const ${group} = stylex.defineVars({`,
      ...inventory
        .filter(entry => entry.group === group)
        .map(({key, value}) => {
          const dark = darkValues.get(`${group}.${key}`);
          return `${JSON.stringify(key)}: ${JSON.stringify(
            dark === undefined
              ? value
              : {default: value, '@media (prefers-color-scheme: dark)': dark}
          )},`;
        }),
      '});',
    ].join('\n')
  ),
].join('\n\n');
const url = new URL('../src/styles/tokens.stylex.ts', import.meta.url);
const formatted = await format(typescript, {
  parser: 'typescript',
  printWidth: 90,
  singleQuote: true,
  bracketSpacing: false,
});
if (process.argv.includes('--check')) {
  if ((await readFile(url, 'utf8')) !== formatted)
    throw new Error('Stale generated tokens: tokens.stylex.ts');
} else {
  await writeFile(url, formatted);
}
