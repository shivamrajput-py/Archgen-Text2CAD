import { ArrowRight, MapPin, Mail, Instagram, Linkedin, Code, Cpu, Database } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function About() {
  return (
    <div className="flex flex-col relative overflow-hidden flex-1">
      
      {/* Minimal Background Effects */}
      <div className="absolute inset-0 blueprint-grid opacity-10 pointer-events-none" />
      <div className="absolute top-[20%] right-[10%] w-[500px] h-[500px] bg-[#5DA9E9]/5 rounded-full blur-[120px] pointer-events-none" />

      <main className="flex-1 pt-32 pb-24 relative z-10 w-full max-w-6xl mx-auto px-6 lg:px-12">
        
        {/* Header */}
        <div className="mb-20 text-center max-w-3xl mx-auto animate-fade-up">
          <div className="inline-flex items-center gap-3 mb-6">
            <div className="w-10 h-px bg-gradient-to-r from-transparent to-[#5DA9E9]/50" />
            <span className="text-xs font-semibold tracking-[0.2em] uppercase text-[#5DA9E9]">Our Mission</span>
            <div className="w-10 h-px bg-gradient-to-l from-transparent to-[#5DA9E9]/50" />
          </div>
          <h1 className="heading-serif text-5xl md:text-6xl text-[#F5F7FA] mb-6">
            Building the future of <span className="gradient-text text-glow">engineering</span>.
          </h1>
          <p className="text-[#AAB4C3] text-lg leading-relaxed">
            Archgen translates intent into precision geometry. We believe that designers and engineers should focus on solving hard problems, while AI handles the structural compilation.
          </p>
        </div>

        {/* Team Section */}
        <section className="mb-24 animate-fade-up" style={{ animationDelay: '0.1s' }}>
          <div className="flex items-center gap-4 border-b border-white/10 pb-4 mb-8">
            <h2 className="text-2xl font-serif text-white">Founders</h2>
          </div>
          
          <div className="grid md:grid-cols-2 gap-8">
            {/* Shivam */}
            <div className="glass-panel p-8 rounded-2xl flex flex-col sm:flex-row gap-6 items-center sm:items-start group hover:border-[#5DA9E9]/30 transition-colors">
              <div className="w-24 h-24 rounded-full bg-gradient-to-br from-[#141B24] to-[#1a2332] border border-white/10 flex items-center justify-center shrink-0">
                <span className="text-2xl font-serif text-[#AAB4C3]">SR</span>
              </div>
              <div className="text-center sm:text-left flex-1">
                <h3 className="text-xl font-medium text-white mb-1">Shivam Rajput</h3>
                <p className="text-sm text-[#5DA9E9] mb-4">Co-Founder</p>
                <div className="flex justify-center sm:justify-start">
                  <a href="https://www.linkedin.com/in/shivam-rajput-3928a328a/" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 text-sm text-[#AAB4C3] hover:text-white transition-colors">
                    <Linkedin size={16} /> Connect on LinkedIn
                  </a>
                </div>
              </div>
            </div>

            {/* Manish */}
            <div className="glass-panel p-8 rounded-2xl flex flex-col sm:flex-row gap-6 items-center sm:items-start group hover:border-[#5DA9E9]/30 transition-colors">
              <div className="w-24 h-24 rounded-full bg-gradient-to-br from-[#141B24] to-[#1a2332] border border-white/10 flex items-center justify-center shrink-0">
                <span className="text-2xl font-serif text-[#AAB4C3]">MN</span>
              </div>
              <div className="text-center sm:text-left flex-1">
                <h3 className="text-xl font-medium text-white mb-1">Manish N</h3>
                <p className="text-sm text-[#5DA9E9] mb-4">Co-Founder</p>
                <div className="flex justify-center sm:justify-start">
                  <a href="https://www.linkedin.com/in/manish-n-111931284/" target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 text-sm text-[#AAB4C3] hover:text-white transition-colors">
                    <Linkedin size={16} /> Connect on LinkedIn
                  </a>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Company & Backers */}
        <section className="mb-24 animate-fade-up" style={{ animationDelay: '0.2s' }}>
          <div className="grid md:grid-cols-2 gap-12">
            {/* Tech */}
            <div>
              <div className="flex items-center gap-4 border-b border-white/10 pb-4 mb-6">
                <h2 className="text-2xl font-serif text-white">Technology</h2>
              </div>
              <div className="space-y-4">
                <div className="flex items-center gap-4 text-[#AAB4C3]">
                  <div className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center border border-white/5">
                    <Code size={18} className="text-[#5DA9E9]" />
                  </div>
                  <span>Generative AI constraint compilation</span>
                </div>
                <div className="flex items-center gap-4 text-[#AAB4C3]">
                  <div className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center border border-white/5">
                    <Cpu size={18} className="text-[#5DA9E9]" />
                  </div>
                  <span>Parametric logic via proprietary CAD engine</span>
                </div>
                <div className="flex items-center gap-4 text-[#AAB4C3]">
                  <div className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center border border-white/5">
                    <Database size={18} className="text-[#5DA9E9]" />
                  </div>
                  <span>Real-time STEP and STL exports</span>
                </div>
              </div>
            </div>

            {/* Backers */}
            <div>
              <div className="flex items-center gap-4 border-b border-white/10 pb-4 mb-6">
                <h2 className="text-2xl font-serif text-white">Backed By</h2>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="glass-panel px-6 py-4 rounded-xl flex items-center justify-center h-20 border-white/5 text-center text-[#F5F7FA] font-medium tracking-wide">
                  DTU IIF
                </div>
                <div className="glass-panel px-6 py-4 rounded-xl flex items-center justify-center h-20 border-white/5 text-center text-[#F5F7FA] font-medium tracking-wide">
                  Ciena
                </div>
                <div className="glass-panel px-6 py-4 rounded-xl sm:col-span-2 flex items-center justify-center h-20 border-white/5 text-center text-[#F5F7FA] font-medium tracking-wide">
                  Nasscom Foundation
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Contact info */}
        <section className="animate-fade-up" style={{ animationDelay: '0.3s' }}>
          <div className="glass-panel p-8 md:p-12 rounded-2xl relative overflow-hidden">
            {/* Soft background glow */}
            <div className="absolute inset-0 bg-gradient-to-br from-[#5DA9E9]/10 to-transparent opacity-50 pointer-events-none" />
            
            <div className="relative z-10 grid md:grid-cols-2 gap-12 items-center">
              <div>
                <h2 className="text-3xl font-serif text-white mb-4">Archgen AI Labs Pvt. Ltd.</h2>
                <div className="space-y-4">
                  <div className="flex items-start gap-3 text-[#AAB4C3]">
                    <MapPin size={20} className="shrink-0 text-[#5DA9E9] mt-1" />
                    <p className="leading-relaxed">
                      AB4 8th floor Office, DTU<br />
                      Delhi Technological University
                    </p>
                  </div>
                  <div className="flex items-center gap-3 text-[#AAB4C3]">
                    <Mail size={20} className="shrink-0 text-[#5DA9E9]" />
                    <a href="mailto:contact@archgen.ai" className="hover:text-white transition-colors">contact@archgen.ai</a>
                  </div>
                </div>
                
                {/* Socials */}
                <div className="flex gap-4 mt-8">
                  <a href="#" className="w-10 h-10 rounded-full bg-white/5 border border-white/10 flex items-center justify-center hover:bg-white/10 hover:border-[#5DA9E9]/50 transition-all text-[#AAB4C3] hover:text-white">
                    <Linkedin size={18} />
                  </a>
                  <a href="#" className="w-10 h-10 rounded-full bg-white/5 border border-white/10 flex items-center justify-center hover:bg-white/10 hover:border-[#5DA9E9]/50 transition-all text-[#AAB4C3] hover:text-white">
                    <Instagram size={18} />
                  </a>
                </div>
              </div>
              
              <div className="flex justify-start md:justify-end">
                <Link to="/studio" className="btn-primary btn-glow px-8 py-4 inline-flex items-center gap-2">
                  Launch Studio <ArrowRight size={18} />
                </Link>
              </div>
            </div>
          </div>
        </section>

      </main>


    </div>
  );
}
