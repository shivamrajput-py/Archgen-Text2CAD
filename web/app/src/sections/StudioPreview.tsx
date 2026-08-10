import { ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';

export function StudioPreview() {
  return (
    <section className="py-24 bg-[#0D1117] relative z-20">
      <div className="max-w-6xl mx-auto px-6">

        {/* Header */}
        <div className="text-center mb-14">
          <div className="inline-flex items-center gap-3 mb-4">
            <span className="text-xs font-semibold tracking-[0.2em] uppercase text-[#5DA9E9]">Interface</span>
          </div>
          <h2 className="heading-serif text-4xl mb-3 text-[#F5F7FA]">
            Archgen Studio
          </h2>
          <p className="text-[#6E7A8A] text-lg max-w-2xl mx-auto">
            A glimpse into your parametric workspace.
          </p>
        </div>

        {/* Browser Mockup Image containing actual screenshot */}
        <div className="max-w-5xl mx-auto rounded-xl overflow-hidden border border-white/10 shadow-2xl bg-[#11161D]">
          {/* Browser Chrome */}
          <div className="bg-[#141B24] border-b border-white/5 px-4 py-3 flex items-center gap-4">
            <div className="flex gap-1.5">
              <div className="w-3 h-3 rounded-full bg-white/10" />
              <div className="w-3 h-3 rounded-full bg-white/10" />
              <div className="w-3 h-3 rounded-full bg-white/10" />
            </div>
            <div className="flex-1 mx-4 h-6 bg-white/5 rounded border border-white/5 flex items-center justify-center">
              <span className="text-[11px] font-mono text-[#6E7A8A] tracking-wider">archgen.ai/studio</span>
            </div>
            <div className="w-[52px]" /> {/* Spacer to balance dots */}
          </div>

          {/* Actual Studio Screenshot */}
          <div className="aspect-[16/9] w-full bg-[#0D1117] flex items-center justify-center relative">
            <img 
              src="/studio-preview.png" 
              alt="Archgen Studio Interface Preview" 
              className="w-full h-full object-cover"
              onError={(e) => {
                // Fallback text if the screenshot hasn't been added to public/ yet
                const target = e.target as HTMLImageElement;
                target.style.display = 'none';
                if (target.nextElementSibling) {
                  (target.nextElementSibling as HTMLElement).style.display = 'flex';
                }
              }}
            />
            {/* Fallback state shown only if image fails to load */}
            <div className="absolute inset-0 hidden flex-col items-center justify-center text-center p-6 border border-dashed border-white/10 m-8 rounded-lg bg-white/[0.02]">
              <span className="text-sm text-[#6E7A8A] font-mono mb-2">[Image Placeholder]</span>
              <p className="text-[#AAB4C3] text-sm">Please save a screenshot of the Studio to <br/>`web/app/public/studio-preview.png`</p>
            </div>
          </div>
        </div>

        {/* CTA */}
        <div className="mt-12 text-center">
          <Link
            to="/studio"
            className="inline-flex items-center gap-2 text-sm font-medium text-[#F5F7FA] bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg px-6 py-3 transition-colors"
          >
            Launch Workspace
            <ArrowRight size={16} />
          </Link>
        </div>
      </div>
    </section>
  );
}
