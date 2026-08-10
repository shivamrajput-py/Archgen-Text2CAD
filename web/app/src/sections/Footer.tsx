import { Link } from 'react-router-dom';
import { Github, Twitter } from 'lucide-react';

export function Footer() {
  return (
    <footer className="relative bg-[#0A0D14] border-t border-white/5 py-12 lg:py-16">
      <div className="max-w-7xl mx-auto px-6 lg:px-12 flex flex-col md:flex-row justify-between items-start gap-12">
        {/* Brand */}
        <div className="flex flex-col gap-4 max-w-sm">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#5DA9E9] to-[#667eea] flex items-center justify-center">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5">
                <path d="M3 21l9-18 9 18" />
              </svg>
            </div>
            <span className="text-lg font-bold tracking-[0.1em] text-[#F5F7FA]">ARCHGEN</span>
          </Link>
          <p className="text-[#6E7A8A] text-sm leading-relaxed">
            State-of-the-art Text to CAD model — from words to precision geometry. Engineering intuition transformed into structural reality.
          </p>
          <div className="flex items-center gap-3 pt-2">
            <a href="https://github.com" target="_blank" rel="noopener noreferrer" className="text-[#6E7A8A] hover:text-white transition-colors">
              <Github size={18} />
            </a>
            <a href="https://twitter.com" target="_blank" rel="noopener noreferrer" className="text-[#6E7A8A] hover:text-white transition-colors">
              <Twitter size={18} />
            </a>
          </div>
        </div>

        {/* Links */}
        <div className="grid grid-cols-2 gap-12 sm:gap-24">
          <div className="flex flex-col gap-3">
            <span className="font-mono text-xs uppercase tracking-widest text-[#5DA9E9] mb-2">Product</span>
            <Link to="/studio" className="text-sm text-[#AAB4C3] hover:text-white transition-colors">Studio</Link>
            <Link to="/demo" className="text-sm text-[#AAB4C3] hover:text-white transition-colors">View Demo</Link>
            <Link to="/archgencad" className="text-sm text-[#AAB4C3] hover:text-white transition-colors">Features</Link>
          </div>
          <div className="flex flex-col gap-3">
            <span className="font-mono text-xs uppercase tracking-widest text-[#5DA9E9] mb-2">Company</span>
            <Link to="/about" className="text-sm text-[#AAB4C3] hover:text-white transition-colors">About Us</Link>
            <Link to="/services" className="text-sm text-[#AAB4C3] hover:text-white transition-colors">Services</Link>
            <Link to="/signin" className="text-sm text-[#AAB4C3] hover:text-white transition-colors">Sign In</Link>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 lg:px-12 mt-12 pt-8 border-t border-white/5 flex flex-col md:flex-row items-center justify-between gap-4">
        <p className="text-xs text-[#6E7A8A]">© {new Date().getFullYear()} Archgen AI Labs Pvt. Ltd. All rights reserved.</p>
        <div className="flex items-center gap-6">
          <a href="#" className="text-xs text-[#6E7A8A] hover:text-white transition-colors">Privacy Policy</a>
          <a href="#" className="text-xs text-[#6E7A8A] hover:text-white transition-colors">Terms of Service</a>
        </div>
      </div>
    </footer>
  );
}
