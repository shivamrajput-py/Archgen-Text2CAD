import { ArrowRight, Lock, Mail } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { login } from '../services/api';

export default function SignIn() {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const data = await login(username, password);
      localStorage.setItem('archgen_auth', 'true');
      localStorage.setItem('archgen_token', data.token);
      localStorage.setItem('archgen_limit', data.limit.toString());
      localStorage.setItem('archgen_user', username);
      navigate('/studio');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-6 relative overflow-hidden">
      {/* Minimal Background Effects */}
      <div className="absolute inset-0 blueprint-grid opacity-10 pointer-events-none" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-[#5DA9E9]/5 rounded-full blur-[100px] pointer-events-none" />
      
      <div className="w-full max-w-sm relative z-10 animate-fade-up">

        <div className="glass-panel p-8 rounded-2xl border border-white/10 bg-[#11161D]/60 backdrop-blur-xl shadow-2xl">
          <div className="flex flex-col items-center mb-8">
            <div className="w-12 h-12 bg-white/5 rounded-full flex items-center justify-center mb-4 border border-white/10 shadow-inner">
              <Lock className="text-[#5DA9E9] w-5 h-5" />
            </div>
            <h1 className="text-2xl font-serif text-white">Welcome Back</h1>
            <p className="text-[#AAB4C3] text-sm mt-2 text-center">Sign in to access Archgen Studio</p>
          </div>

          <div className="space-y-4">
            <div className="relative pb-6">
              <div className="text-[#AAB4C3] text-sm text-center">
                Private Beta Access
              </div>
            </div>

            <form onSubmit={handleSignIn} className="space-y-4">
              {error && (
                <div className="bg-red-500/10 border border-red-500/50 text-red-500 rounded-lg px-4 py-2 text-sm text-center">
                  {error}
                </div>
              )}
              <div>
                <input 
                  type="text" 
                  placeholder="Username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-3 text-white placeholder-white/30 focus:outline-none focus:border-[#5DA9E9] transition-colors"
                  required
                />
              </div>
              <div>
                <input 
                  type="password" 
                  placeholder="Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-black/20 border border-white/10 rounded-lg px-4 py-3 text-white placeholder-white/30 focus:outline-none focus:border-[#5DA9E9] transition-colors"
                  required
                />
              </div>
              <button type="submit" disabled={loading} className="w-full btn-secondary py-3 flex items-center justify-center gap-2">
                {loading ? 'Authenticating...' : 'Sign In'}
                {!loading && <ArrowRight className="w-4 h-4" />}
              </button>
            </form>

            <div className="pt-6 border-t border-white/10 mt-6 text-center">
              <p className="text-[#6E7A8A] text-xs">Don't have an account?</p>
              <a 
                href="mailto:contact@archgen.in"
                className="w-full text-sm text-[#5DA9E9] hover:text-[#F5F7FA] transition-colors flex items-center justify-center gap-2 py-2 mt-2"
              >
                <Mail className="w-4 h-4" />
                Contact us for access
              </a>
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}
