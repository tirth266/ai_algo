import React from 'react';

export const Login: React.FC = () => {
  const apiKey = (import.meta as any).env?.VITE_ANGEL_ONE_API_KEY || "LFHr3Azz";
  const redirectUrl = (import.meta as any).env?.VITE_ANGEL_REDIRECT_URL || `${(import.meta as any).env?.VITE_APP_URL}/angel-callback`;
  const encodedRedirect = encodeURIComponent(redirectUrl);
  
  const angelOnePublisherUrl = `https://smartapi.angelone.in/publisher-login?api_key=${apiKey}&redirect_url=${encodedRedirect}`;

  return (
    <div 
      className="flex flex-col items-center justify-center min-h-screen p-6 relative overflow-hidden"
      style={{ backgroundColor: 'var(--bg-primary)' }}
    >
      {/* Decorative Background */}
      <div 
        className="absolute top-0 right-0 p-48 rounded-full pointer-events-none"
        style={{ 
          background: 'radial-gradient(circle, rgba(0, 191, 255, 0.2) 0%, transparent 70%)',
        }}
      ></div>
      <div 
        className="absolute bottom-0 left-0 p-48 rounded-full pointer-events-none"
        style={{ 
          background: 'radial-gradient(circle, rgba(0, 255, 156, 0.15) 0%, transparent 70%)',
        }}
      ></div>

      {/* Glassmorphism Login Card */}
      <div 
        className="glass-card p-10 rounded-2xl max-w-md w-full text-center animate-fade-in"
      >
        {/* Gradient Icon */}
        <div 
          className="w-16 h-16 rounded-full mx-auto mb-6 flex items-center justify-center gradient-glow"
        >
          <svg 
            className="w-8 h-8" 
            fill="none" 
            stroke="#000000" 
            viewBox="0 0 24 24" 
            xmlns="http://www.w3.org/2000/svg"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
        </div>
        
        {/* Gradient Title */}
        <h1 
          className="text-3xl font-bold mb-4 gradient-text"
        >
          Secure Login
        </h1>
        
        <p 
          className="mb-8 leading-relaxed"
          style={{ color: 'var(--text-secondary)' }}
        >
          Authenticate your Angel One account to generate a valid API session and establish real-time market bridges.
        </p>
        
        {/* Gradient Button with Micro-interactions */}
        <a 
          href={angelOnePublisherUrl}
          className="btn btn-micro px-6 py-3 font-semibold rounded-lg block w-full gradient-glow"
        >
          Login to Angel One
        </a>
      </div>
    </div>
  );
};