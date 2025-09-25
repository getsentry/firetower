import {describe, expect, it} from 'bun:test';

import {cn} from './cn';

describe('cn utility', () => {
  describe('classnames functionality', () => {
    it('should render design token styles conditionally', () => {
      const className = cn('text-content-primary', {
        'bg-background-primary': false,
        'bg-background-accent-vibrant': true,
      });

      expect(className).toEqual('text-content-primary bg-background-accent-vibrant');
    });

    it('should handle many design token arguments', () => {
      const className = cn(
        'text-size-md text-content-headings',
        {
          'bg-background-secondary': false,
          'bg-background-success-vibrant': true,
        },
        'rounded-radius-lg',
        {'shadow-sm': null},
        null
      );

      expect(className).toEqual('text-size-md text-content-headings bg-background-success-vibrant rounded-radius-lg');
    });

    it('should flatten arrays with design token classes', () => {
      const arr = ['p-space-md', {'m-space-xl': true, 'border-primary': false}];
      const className = cn('bg-background-tertiary', arr);

      expect(className).toEqual('bg-background-tertiary p-space-md m-space-xl');
    });

    it('should work with spacing design tokens', () => {
      const className = cn({
        'p-space-2xl': true,
        'mb-space-xl': true,
        'px-space-sm': false,
      });

      expect(className).toEqual('p-space-2xl mb-space-xl');
    });
  });

  describe('design token merging functionality', () => {
    it('should merge conflicting background classes', () => {
      const className = cn(
        'bg-background-primary hover:bg-background-secondary px-space-xs py-space-sm',
        'bg-background-accent-vibrant p-space-lg'
      );

      expect(className).toEqual('hover:bg-background-secondary bg-background-accent-vibrant p-space-lg');
    });

    it('should merge conflicting text classes', () => {
      const className = cn(
        'text-content-primary text-size-md',
        'text-content-accent text-size-lg'
      );

      expect(className).toEqual('text-content-accent text-size-lg');
    });

    it('should merge conflicting spacing classes', () => {
      const className = cn(
        'p-space-sm mb-space-md',
        'p-space-xl mb-space-lg'
      );

      expect(className).toEqual('p-space-xl mb-space-lg');
    });

    it('should merge conflicting border radius classes', () => {
      const className = cn(
        'rounded-radius-sm border-primary',
        'rounded-radius-lg border-accent-muted'
      );

      expect(className).toEqual('rounded-radius-lg border-accent-muted');
    });

    it('should still merge standard Tailwind classes', () => {
      const className = cn(
        'bg-red-500 hover:bg-red-600 px-2 py-1',
        'bg-blue-500 p-4'
      );

      expect(className).toEqual('hover:bg-red-600 bg-blue-500 p-4');
    });
  });

  describe('real-world component scenarios', () => {
    it('should handle button-like component classes', () => {
      const isActive = true;
      const isDisabled = false;

      const className = cn(
        'px-space-lg py-space-md rounded-radius-md text-size-md font-medium',
        {
          'bg-background-accent-vibrant text-content-on-vibrant-light': isActive,
          'bg-background-secondary text-content-secondary': !isActive && !isDisabled,
          'bg-background-tertiary text-content-disabled': isDisabled,
        }
      );

      expect(className).toEqual('px-space-lg py-space-md rounded-radius-md text-size-md font-medium bg-background-accent-vibrant text-content-on-vibrant-light');
    });

    it('should handle card-like component classes', () => {
      const hasError = false;

      const className = cn(
        'bg-background-primary rounded-radius-lg p-space-2xl',
        {
          'border-accent-muted': !hasError,
          'border-danger-vibrant': hasError,
        },
        'shadow-sm'
      );

      expect(className).toEqual('bg-background-primary rounded-radius-lg p-space-2xl border-accent-muted shadow-sm');
    });
  });
});
