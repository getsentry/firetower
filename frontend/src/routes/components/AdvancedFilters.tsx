import {Card} from 'components/Card';

import {ServiceTierSchema, SeveritySchema} from '../types';

import {DateRangeFilter} from './filters/DateRangeFilter';
import {PillFilter} from './filters/PillFilter';
import {TagFilter} from './filters/TagFilter';
import {UserFilter} from './filters/UserFilter';

export {FilterTrigger} from './filters/FilterTrigger';

export function FilterPanel() {
  return (
    <Card className="flex flex-col gap-space-md" data-testid="advanced-filters">
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-space-md">
        <PillFilter
          label="Severity"
          filterKey="severity"
          options={SeveritySchema.options}
        />
        <PillFilter
          label="Service Tier"
          filterKey="service_tier"
          options={ServiceTierSchema.options}
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
        <DateRangeFilter />
      </div>
    </Card>
  );
}
