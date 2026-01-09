import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {render, screen} from '@testing-library/react';

import type {IncidentDetail} from '../queries/incidentDetailQueryOptions';

import {IncidentSummary} from './IncidentSummary';

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {retry: false},
      mutations: {retry: false},
    },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

const mockIncident: IncidentDetail = {
  id: 'INC-123',
  title: 'Test Incident',
  description: 'This is a test incident description',
  impact_summary: 'Users experiencing 500 errors',
  status: 'Active',
  severity: 'P1',
  service_tier: null,
  created_at: '2024-01-01T12:00:00Z',
  updated_at: '2024-01-01T12:00:00Z',
  is_private: false,
  affected_area_tags: ['API', 'Database'],
  root_cause_tags: ['Resource Exhaustion'],
  impact_type_tags: [],
  participants: [],
  external_links: {
    slack: null,
    jira: null,
    datadog: null,
    pagerduty: null,
    statuspage: null,
    notion: null,
    linear: null,
  },
  time_started: null,
  time_detected: null,
  time_analyzed: null,
  time_mitigated: null,
  time_recovered: null,
};

describe('IncidentSummary', () => {
  it('renders incident title and description', () => {
    renderWithQueryClient(<IncidentSummary incident={mockIncident} />);

    expect(screen.getByText('Test Incident')).toBeInTheDocument();
    expect(screen.getByText('This is a test incident description')).toBeInTheDocument();
  });

  it('renders incident ID', () => {
    renderWithQueryClient(<IncidentSummary incident={mockIncident} />);

    expect(screen.getByText('INC-123')).toBeInTheDocument();
  });

  it('renders severity and status pills', () => {
    renderWithQueryClient(<IncidentSummary incident={mockIncident} />);

    expect(screen.getByText('P1')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('renders private badge when incident is private', () => {
    const privateIncident = {...mockIncident, is_private: true};
    renderWithQueryClient(<IncidentSummary incident={privateIncident} />);

    expect(screen.getByText('Private')).toBeInTheDocument();
    expect(screen.getByLabelText('Private incident')).toBeInTheDocument();
  });

  it('does not render private badge when incident is not private', () => {
    renderWithQueryClient(<IncidentSummary incident={mockIncident} />);

    expect(screen.queryByText('Private')).not.toBeInTheDocument();
  });

  describe('Impact summary section', () => {
    it('renders impact summary when present', () => {
      renderWithQueryClient(<IncidentSummary incident={mockIncident} />);

      expect(screen.getByText('Impact summary')).toBeInTheDocument();
      expect(screen.getByText('Users experiencing 500 errors')).toBeInTheDocument();
    });

    it('renders editable field when impact summary is empty', () => {
      const incidentWithoutImpact = {...mockIncident, impact_summary: ''};
      renderWithQueryClient(<IncidentSummary incident={incidentWithoutImpact} />);

      expect(screen.getByText('Impact summary')).toBeInTheDocument();
      const editButtons = screen.getAllByRole('button', {name: 'Edit'});
      expect(editButtons.length).toBeGreaterThan(0);
    });
  });

  describe('Affected areas section', () => {
    it('renders affected areas when present', () => {
      renderWithQueryClient(<IncidentSummary incident={mockIncident} />);

      expect(screen.getByText('Affected areas')).toBeInTheDocument();
      expect(screen.getByText('API')).toBeInTheDocument();
      expect(screen.getByText('Database')).toBeInTheDocument();
    });

    it('renders empty state when no affected areas', () => {
      const incidentWithoutAreas = {...mockIncident, affected_area_tags: []};
      renderWithQueryClient(<IncidentSummary incident={incidentWithoutAreas} />);

      expect(screen.getByText('Affected areas')).toBeInTheDocument();
      expect(screen.getByText('No affected areas specified')).toBeInTheDocument();
    });
  });

  describe('Root cause section', () => {
    it('renders root causes when present', () => {
      renderWithQueryClient(<IncidentSummary incident={mockIncident} />);

      expect(screen.getByText('Root cause')).toBeInTheDocument();
      expect(screen.getByText('Resource Exhaustion')).toBeInTheDocument();
    });

    it('renders empty state when no root causes', () => {
      const incidentWithoutCauses = {...mockIncident, root_cause_tags: []};
      renderWithQueryClient(<IncidentSummary incident={incidentWithoutCauses} />);

      expect(screen.getByText('Root cause')).toBeInTheDocument();
      expect(screen.getByText('No root cause specified')).toBeInTheDocument();
    });

    it('renders multiple root causes', () => {
      const incidentWithMultipleCauses = {
        ...mockIncident,
        root_cause_tags: ['Resource Exhaustion', 'Traffic Spike', 'Configuration Error'],
      };
      renderWithQueryClient(<IncidentSummary incident={incidentWithMultipleCauses} />);

      expect(screen.getByText('Resource Exhaustion')).toBeInTheDocument();
      expect(screen.getByText('Traffic Spike')).toBeInTheDocument();
      expect(screen.getByText('Configuration Error')).toBeInTheDocument();
    });
  });

  it('formats the created_at timestamp', () => {
    renderWithQueryClient(<IncidentSummary incident={mockIncident} />);

    const timeElement = screen.getByText(/Jan 1, 2024/);
    expect(timeElement).toBeInTheDocument();
  });
});
