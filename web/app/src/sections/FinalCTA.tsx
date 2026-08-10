import { ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';

export function FinalCTA() {
  return (
    <section className="py-24 lg:py-32 bg-[#0D1117] border-t border-white/5 relative z-20">
      <div className="max-w-4xl mx-auto px-6 text-center">
        {/* Heading */}
        <h2 className="heading-serif text-4xl sm:text-5xl lg:text-6xl text-[#F5F7FA] mb-6 leading-tight">
          Ready to Transform<br />
          <span className="text-[#5DA9E9]">Your Design Process?</span>
        </h2>

        {/* Description */}
        <p className="text-[#AAB4C3] text-lg max-w-2xl mx-auto mb-10 leading-relaxed">
          Join engineers and architects who are already using Archgen to accelerate their workflow. From concept to manufacture in minutes.
        </p>

        {/* CTA Buttons */}
        <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
          <Link
            to="/studio"
            className="btn-primary btn-glow px-8 py-3 flex items-center gap-2 font-medium"
          >
            Open Studio
            <ArrowRight size={18} />
          </Link>

          <Link
            to="/demo"
            className="text-[#AAB4C3] hover:text-[#F5F7FA] text-sm transition-colors px-6 py-3 border border-transparent hover:border-white/10 rounded-lg flex items-center gap-2"
          >
            View Examples
          </Link>
        </div>
      </div>
    </section>
  );
}
