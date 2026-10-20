import * as stylex from '@stylexjs/stylex';
import {Card} from 'components/Card';

import {space} from '../../styles/tokens.stylex';
import {ServiceTierSchema, SeveritySchema} from '../types';

import {DateRangeFilter} from './filters/DateRangeFilter';
import {PillFilter} from './filters/PillFilter';
import {TagFilter} from './filters/TagFilter';
import {UserFilter} from './filters/UserFilter';

export {FilterTrigger} from './filters/FilterTrigger';

export function FilterPanel() {
  return (
    <Card style={styles.panel} data-testid="advanced-filters">
      <div {...stylex.props(styles.grid)}>
        <PillFilter
          label="Severity"
          filterKey="severity"
          options={SeveritySchema.options}
        />
        <PillFilter
          label="Service Tier"
          filterKey="service_tier"
          options={ServiceTierSchema.options}
          allowEmpty
        />
        <TagFilter label="Impact Type" filterKey="impact_type" tagType="IMPACT_TYPE" />
        <TagFilter
          label="Affected Service"
          filterKey="affected_service"
          tagType="AFFECTED_SERVICE"
        />
        <TagFilter
          label="Affected Region"
          filterKey="affected_region"
          tagType="AFFECTED_REGION"
        />
        <TagFilter label="Root Cause" filterKey="root_cause" tagType="ROOT_CAUSE" />
        <UserFilter label="Captain" filterKey="captain" />
        <UserFilter label="Reporter" filterKey="reporter" />
        <UserFilter label="Participant" filterKey="participant" />
        <DateRangeFilter />
      </div>
    </Card>
  );
}

const styles = stylex.create({
  panel: {gap: space.md, display: 'flex', flexDirection: 'column'},
  grid: {
    gap: space.md,
    display: 'grid',
    gridTemplateColumns: {
      default: 'repeat(1, minmax(0, 1fr))',
      '@media (min-width: 640px)': 'repeat(2, minmax(0, 1fr))',
      '@media (min-width: 1280px)': 'repeat(3, minmax(0, 1fr))',
    },
  },
});
