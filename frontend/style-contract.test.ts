import path from 'node:path';

import {ESLint} from 'eslint';
import ts from 'typescript';
import {describe, expect, it} from 'vitest';

function typeErrors(source: string) {
  const filename = path.resolve('src/styles/__style_contract.tsx');
  const config = ts.readConfigFile('tsconfig.app.json', ts.sys.readFile);
  const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, process.cwd());
  const options = {...parsed.options, incremental: false, noEmit: true};
  const host = ts.createCompilerHost(options);
  const original = host.getSourceFile.bind(host);
  host.getSourceFile = (name, languageVersion, onError, shouldCreateNewSourceFile) =>
    name === filename
      ? ts.createSourceFile(name, source, languageVersion, true, ts.ScriptKind.TSX)
      : original(name, languageVersion, onError, shouldCreateNewSourceFile);
  const program = ts.createProgram([filename], options, host);
  return ts.getPreEmitDiagnostics(program).map(error => ({
    file: error.file?.fileName,
    line:
      error.file && error.start !== undefined
        ? error.file.getLineAndCharacterOfPosition(error.start).line
        : -1,
    message: ts.flattenDiagnosticMessageText(error.messageText, '\n'),
  }));
}

const imports = `
import * as stylex from '@stylexjs/stylex';
import type {CSSProperties} from 'react';
import {Button} from '../components/Button';
import {Pill} from '../components/Pill';
import {Calendar} from '../components/Calendar';
import {PopoverContent} from '../components/Popover';
const styles = stylex.create({base: {color: 'red'}, dynamic: (width: number) => ({width})});
`;

describe('StyleX styling contract', () => {
  it('accepts compiled styles and preserves Calendar selection inference', () => {
    const source =
      imports.replace("import type {CSSProperties} from 'react';", '') +
      `
export const examples = [
  <Button style={styles.base} />,
  <Pill style={[styles.base, false, null, undefined, styles.dynamic(20)]}>P1</Pill>,
  <PopoverContent style={styles.base} />,
  <Calendar mode="range" selected={{from: new Date()}} onSelect={range => { range?.from?.getTime(); }} />,
];
`;
    expect(typeErrors(source)).toEqual([]);
  });

  it('rejects raw CSS and class strings at component boundaries', () => {
    const cases = [
      '<Button className="raw" />',
      '<Button style={{color: "red"}} />',
      '<Pill style={raw}>P1</Pill>',
      '<PopoverContent style={{padding: 8}} />',
      '<Button {...classProps} />',
      '<Button {...stylex.props(styles.base)} />',
      '<Calendar mode="range" classNames={{root: "raw"}} />',
      '<Calendar mode="range" styles={{root: {color: "red"}}} />',
      '<Calendar mode="range" modifiersStyles={{selected: {color: "red"}}} />',
      '<Calendar mode="range" {...calendarClasses} />',
      '<Calendar mode="range" {...calendarStyles} />',
    ];
    const prefix =
      imports +
      '\nconst raw: CSSProperties = {color: "red"};\nconst classProps = {className: "raw"};\nconst calendarClasses = {classNames: {root: "raw"}};\nconst calendarStyles = {styles: {root: {color: "red"}}};\n';
    const source =
      prefix +
      cases.map((value, index) => `export const invalid${index} = ${value};`).join('\n');
    const errors = typeErrors(source);
    const start = prefix.split('\n').length - 1;
    for (let index = 0; index < cases.length; index++) {
      expect(
        errors.some(error => error.line === start + index),
        cases[index]
      ).toBe(true);
    }
  });

  it('rejects authored classes, inline host styles, and generated DOM props on app components', async () => {
    const eslint = new ESLint();
    const source = `import * as stylex from '@stylexjs/stylex';
import {Button} from 'components/Button';
export function Invalid() {
  return <><div className="raw" /><div style={{color:'red'}} /><Button {...stylex.props({})} /></>;
}`;
    const [result] = await eslint.lintText(source, {filePath: 'src/style-contract.tsx'});
    expect(
      result.messages.filter(message => message.ruleId === 'local/stylex-only')
    ).toHaveLength(3);
  });

  it('rejects raw host styling factored into object spreads', async () => {
    const eslint = new ESLint();
    const source = `import * as stylex from '@stylexjs/stylex';
import {Button} from 'components/Button';
const styles = stylex.create({base: {color: 'red'}});
export function Invalid() {
  const raw = {style: {color:'red'}, className:'raw'};
  const nested = {...raw};
  const domProps = stylex.props(styles.base);
  return <><div {...nested} /><Button {...domProps} /><div {...domProps} /><Button {...{style: styles.base}} /></>;
}`;
    const [result] = await eslint.lintText(source, {filePath: 'src/style-contract.tsx'});
    expect(
      result.messages
        .filter(message => message.ruleId === 'local/stylex-only')
        .map(message => message.messageId)
    ).toEqual(['inlineStyle', 'className', 'hostProps']);
  });

  it('rejects typed raw spreads and CSS props on external host components', async () => {
    const eslint = new ESLint();
    const source = `import type {HTMLAttributes} from 'react';
import {Pencil} from 'lucide-react';
export function Invalid() {
  const raw = {color: 'red'};
  const asserted = {style: raw} as const;
  const checked = {style: raw} satisfies HTMLAttributes<HTMLDivElement>;
  return <><div {...asserted} /><div {...checked} /><Pencil style={raw} /></>;
}`;
    const [result] = await eslint.lintText(source, {filePath: 'src/style-contract.tsx'});
    expect(
      result.messages
        .filter(message => message.ruleId === 'local/stylex-only')
        .map(message => message.messageId)
    ).toEqual(['inlineStyle', 'inlineStyle', 'inlineStyle']);
  });

  it('rejects legacy styling imports and component stylesheets', async () => {
    const eslint = new ESLint();
    const [result] = await eslint.lintText(
      `import 'tailwindcss';\nimport 'tailwind-merge';\nimport './component.css';`,
      {filePath: 'src/style-contract.tsx'}
    );
    expect(
      result.messages.filter(message => message.ruleId === 'no-restricted-imports')
    ).toHaveLength(3);
  });
});
