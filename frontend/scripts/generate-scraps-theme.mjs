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

function kebab(value) {
  return value.replaceAll(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase();
}

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
    variable: `--scraps-${[group, ...path].map(kebab).join('-')}`,
    value,
  }));
  if (new Set(entries.map(entry => entry.key)).size !== entries.length) {
    throw new Error(`Duplicate StyleX token in ${group}`);
  }
  return entries;
});
const darkEntries = colorGroups.flatMap(group =>
  leaves(darkTheme.tokens[group]).map(({path, value}) => ({
    variable: `--scraps-${[group, ...path].map(kebab).join('-')}`,
    value,
  }))
);
const lightPaths = inventory
  .filter(entry => colorGroups.includes(entry.group))
  .map(entry => entry.variable)
  .sort();
if (
  JSON.stringify(lightPaths) !==
  JSON.stringify(darkEntries.map(entry => entry.variable).sort())
) {
  throw new Error('Scraps light and dark token paths differ');
}

const css = [
  ':root {',
  ...inventory.map(({variable, value}) => `  ${variable}: ${value};`),
  '}',
  '@media (prefers-color-scheme: dark) {',
  '  :root {',
  ...darkEntries.map(({variable, value}) => `    ${variable}: ${value};`),
  '  }',
  '}',
].join('\n');
const typescript = [
  "import * as stylex from '@stylexjs/stylex';",
  ...Object.keys(groups).map(group =>
    [
      `export const ${group} = stylex.defineVars({`,
      ...inventory
        .filter(entry => entry.group === group)
        .map(({key, variable}) => `${JSON.stringify(key)}: 'var(${variable})',`),
      '});',
    ].join('\n')
  ),
].join('\n\n');
const outputs = [
  ['../src/styles/scraps-theme.css', css, 'css'],
  ['../src/styles/tokens.stylex.ts', typescript, 'typescript'],
];

for (const [path, source, parser] of outputs) {
  const url = new URL(path, import.meta.url);
  const formatted = await format(source, {parser, printWidth: 90, singleQuote: true});
  if (process.argv.includes('--check')) {
    if ((await readFile(url, 'utf8')) !== formatted)
      throw new Error(`Stale generated tokens: ${path}`);
  } else {
    await writeFile(url, formatted);
  }
}
