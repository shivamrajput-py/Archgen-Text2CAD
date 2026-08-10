import { useState, useEffect } from 'react';
import { Menu, X, User } from 'lucide-react';
import { Link } from 'react-router-dom';

export function Navigation() {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const navLinks = [
    { label: 'VIEW DEMO', href: '/demo' },
    { label: 'FEATURES', href: '#features' },
    { label: 'SERVICES', href: '/services' },
    { label: 'ABOUT', href: '/about' },
    { label: 'SIGN IN', href: '/signin' },
  ];

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        isScrolled
          ? 'bg-[#0D1117]/90 backdrop-blur-md'
          : 'bg-transparent'
      }`}
    >
      <div className="w-full px-6 lg:px-12 xl:px-16">
        <div className="flex items-center justify-between h-16 lg:h-20">
          {/* Logo */}
          <Link
            to="/"
            className="text-[#F5F7FA] font-medium text-lg tracking-[0.08em] hover:opacity-90 transition-opacity"
          >
            ARCHGEN
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center gap-8 lg:gap-10">
            {navLinks.map((link) => (
              link.href.startsWith('/') ? (
                <Link
                  key={link.label}
                  to={link.href}
                  className="nav-link uppercase"
                >
                  {link.label}
                </Link>
              ) : (
                <a
                  key={link.label}
                  href={link.href}
                  className="nav-link uppercase"
                >
                  {link.label}
                </a>
              )
            ))}
          </div>

          {/* Right Actions */}
          <div className="flex items-center gap-4">
            <button
              className="hidden sm:flex w-8 h-8 rounded-full bg-[#1a1f28] items-center justify-center text-[#AAB4C3] hover:text-[#F5F7FA] transition-colors"
              aria-label="Profile"
            >
              <User className="w-4 h-4" strokeWidth={1.5} />
            </button>

            {/* Mobile Menu Button */}
            <button
              className="md:hidden p-2 text-[#AAB4C3] hover:text-[#F5F7FA] transition-colors"
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              aria-label="Toggle menu"
            >
              {isMobileMenuOpen ? (
                <X className="w-5 h-5" strokeWidth={1.5} />
              ) : (
                <Menu className="w-5 h-5" strokeWidth={1.5} />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Menu */}
      <div
        className={`md:hidden absolute top-full left-0 right-0 bg-[#0D1117]/98 backdrop-blur-lg border-t border-white/5 transition-all duration-300 ${
          isMobileMenuOpen
            ? 'opacity-100 translate-y-0'
            : 'opacity-0 -translate-y-4 pointer-events-none'
        }`}
      >
        <div className="px-6 py-6 space-y-4">
          {navLinks.map((link) => (
            link.href.startsWith('/') ? (
              <Link
                key={link.label}
                to={link.href}
                className="block text-[#AAB4C3] hover:text-[#F5F7FA] text-sm tracking-wide transition-colors py-2"
                onClick={() => setIsMobileMenuOpen(false)}
              >
                {link.label}
              </Link>
            ) : (
              <a
                key={link.label}
                href={link.href}
                className="block text-[#AAB4C3] hover:text-[#F5F7FA] text-sm tracking-wide transition-colors py-2"
                onClick={() => setIsMobileMenuOpen(false)}
              >
                {link.label}
              </a>
            )
          ))}
        </div>
      </div>
    </nav>
  );
}
