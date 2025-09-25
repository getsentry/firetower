import { describe, expect, it } from 'bun:test';
import { render, screen } from '@testing-library/react';
import React from 'react';

import { Card } from './Card';

describe('Card Component', () => {
  describe('CardRoot', () => {
    it('should render a card with default styling', () => {
      render(
        <Card data-testid="card">
          <p>Test content</p>
        </Card>
      );

      const card = screen.getByTestId('card');
      expect(card).toBeTruthy();
      expect(card.tagName).toBe('DIV');
    });

    it('should accept custom className', () => {
      render(
        <Card className="custom-class" data-testid="card">
          <p>Test content</p>
        </Card>
      );

      const card = screen.getByTestId('card');
      expect(card.className).toContain('custom-class');
    });

    it('should forward ref correctly', () => {
      const ref = React.createRef<HTMLDivElement>();
      render(
        <Card ref={ref}>
          <p>Test content</p>
        </Card>
      );

      expect(ref.current).toBeTruthy();
      expect(ref.current?.tagName).toBe('DIV');
    });

    it('should pass through HTML attributes', () => {
      render(
        <Card data-testid="card" aria-label="Test card">
          <p>Test content</p>
        </Card>
      );

      const card = screen.getByTestId('card');
      expect(card.getAttribute('aria-label')).toBe('Test card');
    });

    it('should apply CVA classes correctly', () => {
      render(
        <Card data-testid="card">
          <p>Test content</p>
        </Card>
      );

      const card = screen.getByTestId('card');
      const className = card.className;
      
      // Should contain design token classes
      expect(className).toContain('bg-background-primary');
      expect(className).toContain('rounded-radius-lg');
      expect(className).toContain('p-space-2xl');
      expect(className).toContain('shadow-sm');
    });
  });

  describe('Card.Title', () => {
    it('should render a title with default styling', () => {
      render(
        <Card.Title data-testid="title">Test Title</Card.Title>
      );

      const title = screen.getByTestId('title');
      expect(title).toBeTruthy();
      expect(title.tagName).toBe('H3');
      expect(title.textContent).toBe('Test Title');
    });

    it('should accept size variants', () => {
      const { rerender } = render(
        <Card.Title size="sm" data-testid="title">
          Small Title
        </Card.Title>
      );

      const title = screen.getByTestId('title');
      expect(title.className).toContain('text-sm');

      rerender(
        <Card.Title size="xl" data-testid="title">
          Large Title
        </Card.Title>
      );

      expect(title.className).toContain('text-xl');
    });

    it('should use lg size by default', () => {
      render(
        <Card.Title data-testid="title">Default Title</Card.Title>
      );

      const title = screen.getByTestId('title');
      expect(title.className).toContain('text-lg');
    });

    it('should accept custom className', () => {
      render(
        <Card.Title className="custom-title-class" data-testid="title">
          Custom Title
        </Card.Title>
      );

      const title = screen.getByTestId('title');
      expect(title.className).toContain('custom-title-class');
    });

    it('should forward ref correctly', () => {
      const ref = React.createRef<HTMLHeadingElement>();
      render(<Card.Title ref={ref}>Title with ref</Card.Title>);

      expect(ref.current).toBeTruthy();
      expect(ref.current?.tagName).toBe('H3');
    });

    it('should pass through HTML attributes', () => {
      render(
        <Card.Title data-testid="title" aria-level={2}>
          Accessible Title
        </Card.Title>
      );

      const title = screen.getByTestId('title');
      expect(title.getAttribute('aria-level')).toBe('2');
    });

    it('should apply CVA classes correctly', () => {
      render(
        <Card.Title data-testid="title">Styled Title</Card.Title>
      );

      const title = screen.getByTestId('title');
      const className = title.className;
      
      // Should contain design token classes
      expect(className).toContain('text-lg');
      expect(className).toContain('font-semibold');
      expect(className).toContain('mb-space-xl');
      expect(className).toContain('text-content-headings');
    });
  });

  describe('Combined Usage', () => {
    it('should render Card with Title correctly', () => {
      render(
        <Card data-testid="card">
          <Card.Title data-testid="title">Card Title</Card.Title>
          <p data-testid="content">Card content goes here</p>
        </Card>
      );

      const card = screen.getByTestId('card');
      const title = screen.getByTestId('title');
      const content = screen.getByTestId('content');

      expect(card).toBeTruthy();
      expect(title).toBeTruthy();
      expect(content).toBeTruthy();
      expect(title.textContent).toBe('Card Title');
      expect(content.textContent).toBe('Card content goes here');
    });

    it('should render multiple cards independently', () => {
      render(
        <div>
          <Card data-testid="card-1">
            <Card.Title>First Card</Card.Title>
            <p>First content</p>
          </Card>
          <Card data-testid="card-2">
            <Card.Title size="sm">Second Card</Card.Title>
            <p>Second content</p>
          </Card>
        </div>
      );

      const card1 = screen.getByTestId('card-1');
      const card2 = screen.getByTestId('card-2');

      expect(card1).toBeTruthy();
      expect(card2).toBeTruthy();
      expect(screen.getByText('First Card')).toBeTruthy();
      expect(screen.getByText('Second Card')).toBeTruthy();
    });

    it('should work with different title sizes in same card', () => {
      render(
        <Card data-testid="card">
          <Card.Title size="xl" data-testid="main-title">
            Main Title
          </Card.Title>
          <Card.Title size="sm" data-testid="sub-title">
            Subtitle
          </Card.Title>
          <p>Content</p>
        </Card>
      );

      const mainTitle = screen.getByTestId('main-title');
      const subTitle = screen.getByTestId('sub-title');

      expect(mainTitle.className).toContain('text-xl');
      expect(subTitle.className).toContain('text-sm');
    });
  });

  describe('Accessibility', () => {
    it('should have proper displayName for debugging', () => {
      expect(Card.displayName).toBe('Card');
      expect(Card.Title.displayName).toBe('Card.Title');
    });

    it('should render semantic HTML structure', () => {
      render(
        <Card data-testid="semantic-card">
          <Card.Title>Semantic Title</Card.Title>
          <p>Semantic content</p>
        </Card>
      );

      const card = screen.getByTestId('semantic-card');
      const title = screen.getByRole('heading', { level: 3 });
      const content = screen.getByText('Semantic content');

      expect(card).toBeTruthy();
      expect(card.tagName).toBe('DIV');
      expect(title).toBeTruthy();
      expect(title.tagName).toBe('H3');
      expect(content).toBeTruthy();
    });

    it('should support ARIA attributes', () => {
      render(
        <Card aria-label="User information card" role="region">
          <Card.Title aria-describedby="title-description">
            User Profile
          </Card.Title>
          <p id="title-description">Information about the user</p>
        </Card>
      );

      const card = screen.getByRole('region');
      const title = screen.getByRole('heading');

      expect(card.getAttribute('aria-label')).toBe('User information card');
      expect(title.getAttribute('aria-describedby')).toBe('title-description');
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty title', () => {
      render(<Card.Title data-testid="empty-title"></Card.Title>);

      const title = screen.getByTestId('empty-title');
      expect(title.textContent).toBe('');
    });

    it('should handle complex children', () => {
      render(
        <Card data-testid="complex-card">
          <Card.Title>
            Complex <em>formatted</em> title
          </Card.Title>
          <div>
            <p>Nested content</p>
            <button>Action button</button>
          </div>
        </Card>
      );

      const card = screen.getByTestId('complex-card');
      const title = screen.getByRole('heading');
      const button = screen.getByRole('button');

      expect(card).toBeTruthy();
      expect(title.innerHTML).toContain('<em>formatted</em>');
      expect(button.textContent).toBe('Action button');
    });

    it('should handle multiple className merging', () => {
      render(
        <Card className="custom-1 custom-2" data-testid="card">
          <Card.Title className="title-1 title-2" data-testid="title">
            Multiple Classes
          </Card.Title>
        </Card>
      );

      const card = screen.getByTestId('card');
      const title = screen.getByTestId('title');

      expect(card.className).toContain('custom-1');
      expect(card.className).toContain('custom-2');
      expect(title.className).toContain('title-1');
      expect(title.className).toContain('title-2');
    });
  });
});