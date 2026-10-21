import * as stylex from '@stylexjs/stylex';

export const dropdownInputStyles = stylex.create({
  focus: {
    outlineStyle: {default: null, ':focus': 'none'},
  },
});
