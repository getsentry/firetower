import * as stylex from '@stylexjs/stylex';
import {Skeleton} from 'components/Skeleton';

import {radius} from '../../../styles/tokens.stylex';

export const IncidentDetailSkeleton = () => {
  return (
    <div {...stylex.props(styles.page)}>
      <Skeleton style={styles.summary} />
      <div {...stylex.props(styles.columns)}>
        <div {...stylex.props(styles.main)}>
          <Skeleton style={styles.body} />
        </div>
        <aside {...stylex.props(styles.sidebar)}>
          <Skeleton style={styles.shortCard} />
          <Skeleton style={styles.mediumCard} />
          <Skeleton style={styles.summary} />
        </aside>
      </div>
    </div>
  );
};

const styles = stylex.create({
  page: {display: 'flex', flexDirection: 'column', rowGap: '16px', padding: '8px'},
  summary: {
    borderRadius: radius.lg,
    height: '192px',
    width: '100%',
    boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
  },
  columns: {
    display: 'flex',
    flexDirection: {default: 'column', '@media (min-width: 768px)': 'row'},
    gap: '16px',
  },
  main: {flex: {default: null, '@media (min-width: 768px)': '2'}},
  body: {
    borderRadius: radius.lg,
    height: '256px',
    width: '100%',
    boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
  },
  sidebar: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    flex: {default: null, '@media (min-width: 768px)': '1 1 0%'},
  },
  shortCard: {
    borderRadius: radius.lg,
    height: '128px',
    width: '100%',
    boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
  },
  mediumCard: {
    borderRadius: radius.lg,
    height: '160px',
    width: '100%',
    boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
  },
});
