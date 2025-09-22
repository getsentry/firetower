import {Link} from '@tanstack/react-router';

export const Header = () => (
  <nav className="bg-background-primary border-b border-secondary p-space-md">
    <div className="flex items-center justify-center">
      <Link to="/" className="flex items-center gap-space-sm no-underline">
        <img src="/firetower.svg" alt="Firetower" className="h-6 w-6" />
        <span className="text-xl font-medium text-content-headings">Firetower</span>
      </Link>
    </div>
  </nav>
);
