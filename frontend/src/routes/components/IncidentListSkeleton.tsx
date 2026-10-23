import * as stylex from '@stylexjs/stylex';
import {Skeleton} from 'components/Skeleton';

import {radius, space} from '../../styles/tokens.stylex';

export const IncidentListSkeleton = () => {
  return (
    <div {...stylex.props(styles.list)}>
      <Skeleton style={[styles.card, styles.delay(0)]} />
      <Skeleton style={[styles.card, styles.delay(400)]} />
      <Skeleton style={[styles.card, styles.delay(800)]} />
      <Skeleton style={[styles.card, styles.delay(1200)]} />
      <Skeleton style={[styles.card, styles.delay(1600)]} />
    </div>
  );
};

const styles = stylex.create({
  list: {gap: space.lg, display: 'flex', flexDirection: 'column'},
  card: {
    borderRadius: radius.lg,
    height: 128,
    width: '100%',
    boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
  },
  delay: (milliseconds: number) => ({animationDelay: `${milliseconds}ms`}),
});
