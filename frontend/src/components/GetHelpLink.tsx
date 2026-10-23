import * as stylex from '@stylexjs/stylex';

import {content} from '../styles/tokens.stylex';

export const GetHelpLink = () => {
  return (
    <a
      href="https://sentry.slack.com/archives/C08RJKP6NR0"
      target="_blank"
      rel="noopener noreferrer"
      {...stylex.props(styles.link)}
    >
      #team-sre
    </a>
  );
};

const styles = stylex.create({
  link: {
    color: content.accent,
    textDecoration: {default: null, ':hover': 'underline'},
  },
});
