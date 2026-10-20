import {useEffect, useState} from 'react';
import * as stylex from '@stylexjs/stylex';

import {content, space} from '../../../styles/tokens.stylex';

type RedirectProps = {
  redirect?: string;
  message?: string;
  countdown?: number;
};

export const Redirect = ({
  redirect,
  message = 'Redirecting...',
  countdown = 3,
}: RedirectProps) => {
  const [timeRemaining, setTimeRemaining] = useState(countdown);

  useEffect(() => {
    if (!redirect) return;

    if (timeRemaining > 0) {
      const timer = setTimeout(() => {
        setTimeRemaining(timeRemaining - 1);
      }, 1000);
      return () => clearTimeout(timer);
    }

    if (timeRemaining === 0) {
      window.location.href = redirect;
    }
  }, [redirect, timeRemaining]);

  if (redirect) {
    return (
      <div {...stylex.props(styles.container)}>
        <div {...stylex.props(styles.content)}>
          <h2 {...stylex.props(styles.heading)}>{message}</h2>
          <p {...stylex.props(styles.secondary)}>
            You will be redirected in {timeRemaining} second
            {timeRemaining !== 1 ? 's' : ''}
          </p>
          <p {...stylex.props(styles.secondary)}>
            Or,{' '}
            <a href={redirect} {...stylex.props(styles.link)}>
              click here
            </a>{' '}
            to be redirected now.
          </p>
        </div>
      </div>
    );
  }
  return null;
};

const styles = stylex.create({
  container: {
    display: 'flex',
    minHeight: '50vh',
    alignItems: 'center',
    justifyContent: 'center',
  },
  content: {textAlign: 'center'},
  heading: {marginBottom: space.sm},
  secondary: {color: content.secondary},
  link: {color: content.accent},
});
