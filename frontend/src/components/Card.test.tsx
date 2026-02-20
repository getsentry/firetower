import {describe, expect, it} from 'bun:test';

import {render, screen} from '@testing-library/react';

import {Card} from './Card';

describe('Card', () => {
  it('renders arbitrary child', async () => {
    render(<Card>hello</Card>);
    const hello = await screen.findByText('hello');
    expect(hello).toBeInTheDocument();
  });

  describe('Card.Title', () => {
    it('renders', async () => {
      render(
        <Card>
          <Card.Title>Title</Card.Title>
        </Card>
      );
      const title = await screen.findByText('Title');
      expect(title).toBeInTheDocument();
    });
  });
});
