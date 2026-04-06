import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';

import { API_BASE_URL } from '../services/api';

export const AngelOneCallback: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState<string>('Finalizing Session...');

  const authToken = searchParams.get('auth_token');

  useEffect(() => {
    const finalizeSession = async () => {
      if (authToken) {
        localStorage.setItem('angel_one_auth_token', authToken);
        
        try {
          const response = await fetch(`${API_BASE_URL}/api/auth/connect`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ auth_token: authToken }), // Let backend know UI has a token
          });
          
          if (response.ok) {
            setStatus('Session Synchronized Successfully! Redirecting...');
            setTimeout(() => navigate('/dashboard'), 1500); 
          } else {
            setStatus('Setup failed on backend. Please check logs.');
          }
        } catch (error) {
          console.error('Failed to sync session with backend', error);
          setStatus('Backend connection failed.');
        }
      } else {
        setStatus('No auth_token provided in URL.');
      }
    };

    finalizeSession();
  }, [authToken, navigate]);

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-trading-dark text-white p-6 relative overflow-hidden">
      <div className="absolute inset-0 bg-blue-900/5 backdrop-blur-3xl z-0 pointer-events-none"></div>
      
      <div className="bg-gray-800/90 p-8 rounded-2xl shadow-2xl max-w-md w-full text-center border border-gray-700 relative z-10 flex flex-col items-center">
        <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-6"></div>
        <h1 className="text-2xl font-bold mb-4 text-white">
          Angel One Verification
        </h1>
        <p className="text-lg text-blue-400 font-medium">
          {status}
        </p>
      </div>
    </div>
  );
};
