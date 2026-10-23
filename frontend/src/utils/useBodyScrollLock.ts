import {useEffect} from 'react';
import * as stylex from '@stylexjs/stylex';

const styles = stylex.create({
  locked: {overflow: 'hidden'},
});

let locks = 0;

export function useBodyScrollLock(locked: boolean) {
  useEffect(() => {
    if (!locked) return;
    const className = stylex.props(styles.locked).className;
    if (!className) return;
    const classes = className.split(' ');
    locks += 1;
    document.body.classList.add(...classes);
    return () => {
      locks -= 1;
      if (locks === 0) document.body.classList.remove(...classes);
    };
  }, [locked]);
}
