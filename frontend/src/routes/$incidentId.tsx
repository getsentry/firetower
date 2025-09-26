import {useSuspenseQuery} from '@tanstack/react-query';
import {createFileRoute} from '@tanstack/react-router';

import {incidentDetailQueryOptions} from './queries/incidentDetailQueryOptions';

export const Route = createFileRoute('/$incidentId')({
  component: Incident,
  loader: async ({params, context}) =>
    await context.queryClient.ensureQueryData(incidentDetailQueryOptions(params)),
  pendingComponent: () => <p>Loading incident...</p>,
  errorComponent: () => <p>Something went wrong fetching incident.</p>,
});

function Incident() {
  const params = Route.useParams();
  const {data: incident} = useSuspenseQuery(incidentDetailQueryOptions(params));

  return (
    <div className="p-2">
      <h3>
        {incident.id}: {incident.title}
      </h3>
      <div>Status: {incident.status}</div>
      <div>Severity: {incident.severity}</div>
      <div>Created: {incident.created_at}</div>
      <div>Updated: {incident.updated_at}</div>
      <p>{incident.description}</p>

      {incident.participants.length > 0 && (
        <div>
          <h4>Participants</h4>
          {incident.participants.map((participant, index) => (
            <div key={index}>
              {participant.name} ({participant.role || 'Participant'}) - @
              {participant.slack}
            </div>
          ))}
        </div>
      )}

      <div>
        <h4>External Links</h4>
        {incident.external_links.jira && (
          <div>
            <a
              href={incident.external_links.jira}
              target="_blank"
              rel="noopener noreferrer"
            >
              View in Jira
            </a>
          </div>
        )}
      </div>
    </div>
  );
}
