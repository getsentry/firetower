import {Link} from '@tanstack/react-router';

export const Header = () => (
  <nav className="bg-background-primary border-secondary border-b">
    <div className="px-space-md py-space-md md:px-space-xl mx-auto max-w-6xl">
      <div className="flex items-center justify-center">
        <Link to="/" className="gap-space-sm flex items-center no-underline">
          <img src="/firetower.svg" alt="Firetower" className="h-6 w-6" />
          <span className="text-content-headings text-xl font-medium">Firetower</span>
        </Link>
      </div>
    </div>
  </nav>
);
