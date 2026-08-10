import { Cpu, Monitor, Settings2 } from 'lucide-react';

const CORE_CAPABILITIES = [
  {
    title: 'Text-to-CAD Engine',
    icon: Cpu,
    subtitle: 'NLU Parsing Pipeline',
    features: [
      'Semantic structure mapping',
      'Contextual intent recognition',
      'Engineering constraint extraction',
    ],
  },
  {
    title: 'Parametric Modeler',
    icon: Settings2,
    subtitle: 'Parametric Engine',
    features: [
      '100% editable parametric trees',
      'Feature-based history tracking',
      'Design constraint preservation',
    ],
  },
  {
    title: 'Constraint Solver',
    icon: Monitor,
    subtitle: 'Adaptive Layout Intelligence',
    features: [
      'Modular grid scaling',
      'Context-aware layout adaptation',
      'Tolerance-aware modelling',
    ],
  },
];

export function Toolkit() {
  return (
    <section id="features" className="py-24 bg-[#0D1117] border-b border-white/5 relative z-20">
      <div className="max-w-6xl mx-auto px-6">
        
        {/* Section Header */}
        <div className="mb-14">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-xs font-semibold tracking-[0.2em] uppercase text-[#667eea]">Modules</span>
          </div>
          <h2 className="heading-serif text-4xl text-[#F5F7FA] mb-3">Core Capabilities</h2>
          <p className="text-[#6E7A8A] text-lg max-w-xl">
            A toolset built for precision geometry generation.
          </p>
        </div>

        {/* Capabilities Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {CORE_CAPABILITIES.map((cap) => (
            <div key={cap.title} className="bg-[#11161D] border border-white/5 rounded-xl p-8 hover:border-[#667eea]/30 transition-colors">
              <div className="flex items-center gap-4 mb-6">
                <div className="w-12 h-12 rounded-lg bg-[#667eea]/10 flex items-center justify-center border border-[#667eea]/20">
                  <cap.icon size={20} className="text-[#667eea]" />
                </div>
                <div>
                  <h3 className="text-[#F5F7FA] font-medium text-lg leading-tight">{cap.title}</h3>
                  <p className="text-[10px] font-mono tracking-widest text-[#667eea] uppercase mt-1">{cap.subtitle}</p>
                </div>
              </div>

              <ul className="space-y-3">
                {cap.features.map((f) => (
                  <li key={f} className="flex items-start gap-3 text-sm text-[#AAB4C3]">
                    <span className="mt-[6px] w-1.5 h-1.5 rounded-full bg-[#667eea]/50 shrink-0" />
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
