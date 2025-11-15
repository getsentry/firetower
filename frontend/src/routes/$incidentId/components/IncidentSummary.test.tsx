import {render, screen} from '@testing-library/react';

import type {IncidentDetail} from '../queries/incidentDetailQueryOptions';

import {IncidentSummary} from './IncidentSummary';

const mockIncident: IncidentDetail = {
  id: 'INC-123',
  title: 'Test Incident',
  description: 'This is a test incident description',
  impact: 'Users experiencing 500 errors',
  status: 'Active',
  severity: 'P1',
  created_at: '2024-01-01T12:00:00Z',
  updated_at: '2024-01-01T12:00:00Z',
  is_private: false,
  affected_areas: ['API', 'Database'],
  root_causes: ['Resource Exhaustion'],
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
};

describe('IncidentSummary', () => {
  it('renders incident title and description', () => {
    render(<IncidentSummary incident={mockIncident} />);

    expect(screen.getByText('Test Incident')).toBeInTheDocument();
    expect(screen.getByText('This is a test incident description')).toBeInTheDocument();
  });

  it('renders incident ID', () => {
    render(<IncidentSummary incident={mockIncident} />);

    expect(screen.getByText('INC-123')).toBeInTheDocument();
  });

  it('renders severity and status pills', () => {
    render(<IncidentSummary incident={mockIncident} />);

    expect(screen.getByText('P1')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
  });

  it('renders private badge when incident is private', () => {
    const privateIncident = {...mockIncident, is_private: true};
    render(<IncidentSummary incident={privateIncident} />);

    expect(screen.getByText('Private')).toBeInTheDocument();
    expect(screen.getByLabelText('Private incident')).toBeInTheDocument();
  });

  it('does not render private badge when incident is not private', () => {
    render(<IncidentSummary incident={mockIncident} />);

    expect(screen.queryByText('Private')).not.toBeInTheDocument();
  });

  describe('Impact section', () => {
    it('renders impact when present', () => {
      render(<IncidentSummary incident={mockIncident} />);

      expect(screen.getByText('Impact')).toBeInTheDocument();
      expect(screen.getByText('Users experiencing 500 errors')).toBeInTheDocument();
    });

    it('renders empty state when impact is not present', () => {
      const incidentWithoutImpact = {...mockIncident, impact: ''};
      render(<IncidentSummary incident={incidentWithoutImpact} />);

      expect(screen.getByText('Impact')).toBeInTheDocument();
      expect(screen.getByText('No impact specified')).toBeInTheDocument();
    });
  });

  describe('Affected Areas section', () => {
    it('renders affected areas when present', () => {
      render(<IncidentSummary incident={mockIncident} />);

      expect(screen.getByText('Affected Areas')).toBeInTheDocument();
      expect(screen.getByText('API')).toBeInTheDocument();
      expect(screen.getByText('Database')).toBeInTheDocument();
    });

    it('renders empty state when no affected areas', () => {
      const incidentWithoutAreas = {...mockIncident, affected_areas: []};
      render(<IncidentSummary incident={incidentWithoutAreas} />);

      expect(screen.getByText('Affected Areas')).toBeInTheDocument();
      expect(screen.getByText('No affected areas specified')).toBeInTheDocument();
    });
  });

  describe('Root Cause section', () => {
    it('renders root causes when present', () => {
      render(<IncidentSummary incident={mockIncident} />);

      expect(screen.getByText('Root Cause')).toBeInTheDocument();
      expect(screen.getByText('Resource Exhaustion')).toBeInTheDocument();
    });

    it('renders empty state when no root causes', () => {
      const incidentWithoutCauses = {...mockIncident, root_causes: []};
      render(<IncidentSummary incident={incidentWithoutCauses} />);

      expect(screen.getByText('Root Cause')).toBeInTheDocument();
      expect(screen.getByText('No root cause specified')).toBeInTheDocument();
    });

    it('renders multiple root causes', () => {
      const incidentWithMultipleCauses = {
        ...mockIncident,
        root_causes: ['Resource Exhaustion', 'Traffic Spike', 'Configuration Error'],
      };
      render(<IncidentSummary incident={incidentWithMultipleCauses} />);

      expect(screen.getByText('Resource Exhaustion')).toBeInTheDocument();
      expect(screen.getByText('Traffic Spike')).toBeInTheDocument();
      expect(screen.getByText('Configuration Error')).toBeInTheDocument();
    });
  });

  it('formats the created_at timestamp', () => {
    render(<IncidentSummary incident={mockIncident} />);

    const timeElement = screen.getByText(/Jan 1, 2024/);
    expect(timeElement).toBeInTheDocument();
  });
});
