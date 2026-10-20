import React from 'react';
import * as stylex from '@stylexjs/stylex';

import type {StyledProps} from '../styles/props';

import {buttonStyles, type ButtonOptions} from './buttonStyles';
import {Spinner} from './Spinner';

type ButtonProps = StyledProps<React.ButtonHTMLAttributes<HTMLButtonElement>> &
  ButtonOptions & {loading?: boolean; ref?: React.Ref<HTMLButtonElement>};

const Button = ({
  variant,
  size,
  loading,
  disabled,
  children,
  style,
  ref,
  ...props
}: ButtonProps) => (
  <button
    ref={ref}
    type="button"
    disabled={disabled || loading}
    {...stylex.props(buttonStyles({variant, size}), style)}
    {...props}
  >
    {loading ? <Spinner size="sm" /> : children}
  </button>
);

export {Button, type ButtonProps};
