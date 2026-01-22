import {useEffect, useState} from 'react';

type RedirectProps = {
  redirect?: string;
  message?: string;
  countdown?: number; // Countdown duration in seconds
};

export const Redirect = ({
  redirect,
  message = 'Redirecting...',
  countdown = 3,
}: RedirectProps) => {
  const [timeRemaining, setTimeRemaining] = useState(countdown);

  useEffect(() => {
    if (!redirect) return;

    // Countdown timer
    if (timeRemaining > 0) {
      const timer = setTimeout(() => {
        setTimeRemaining(timeRemaining - 1);
      }, 1000);
      return () => clearTimeout(timer);
    }

    // Redirect when countdown reaches 0
    if (timeRemaining === 0) {
      window.location.href = redirect;
    }
  }, [redirect, timeRemaining]);

  // If redirect URL is set, show countdown message
  if (redirect) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <div className="text-center">
          <h2 className="text-heading-sm mb-space-sm">{message}</h2>
          <p className="text-content-secondary">
            You will be redirected in {timeRemaining} second
            {timeRemaining !== 1 ? 's' : ''}
          </p>
          <p className="text-content-secondary">
            Or,{' '}
            <a href={redirect} className="text-content-accent">
              click here
            </a>{' '}
            to be redirected now.
          </p>
        </div>
      </div>
    );
  }
  return null;
};
