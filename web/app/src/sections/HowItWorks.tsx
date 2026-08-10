import { MessageSquare, Cpu, Download } from 'lucide-react';

const PIPELINE = [
  {
    id: '01',
    icon: MessageSquare,
    title: 'Physora Language parsing',
    subtitle: 'Semantic Intent',
    description: 'Deconstructs natural language requirements into machine-parsable architectural constraints.',
  },
  {
    id: '02',
    icon: Cpu,
    title: 'Structural Reasoning Engine',
    subtitle: 'Constraint Extraction',
    description: 'The core Physora engine validates geometry against real-world physics and B-Rep standards.',
  },
  {
    id: '03',
    icon: Download,
    title: 'Parametric Compiler',
    subtitle: 'Geometry Output',
    description: 'Synthesizes validated constraints into production-ready STEP, STL, and OBJ models.',
  },
];

const TECH_SPECS = [
  { label: 'Inference-to-CAD Latency', value: '< 125s' },
  { label: 'Parametric Fidelity', value: 'High' },
  { label: 'Constraint Preservation', value: '100%' },
  { label: 'Export Formats', value: 'STEP | STL | OBJ | IGES' },
];

export function HowItWorks() {
  return (
    <section className="py-24 bg-[#0D1117] border-b border-white/5 relative z-20">
      <div className="max-w-6xl mx-auto px-6">
        {/* Section Header */}
        <div className="mb-16">
          <div className="flex items-center gap-3 mb-4">
            <span className="text-xs font-semibold tracking-[0.2em] uppercase text-[#5DA9E9]">Architecture</span>
          </div>
          <h2 className="heading-serif text-4xl text-[#F5F7FA] mb-3">The Physora Pipeline</h2>
          <p className="text-[#6E7A8A] text-lg max-w-xl">
            From semantic intent to strictly validated physics-ready geometry.
          </p>
        </div>

        {/* Minimal Pipeline Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-12 mb-16">
          {PIPELINE.map((stage) => {
            const Icon = stage.icon;
            return (
              <div key={stage.id} className="flex flex-col gap-4">
                <div className="flex items-center gap-4 border-b border-white/5 pb-4">
                  <div className="text-xs font-mono text-[#5DA9E9]">[{stage.id}]</div>
                  <Icon size={16} className="text-[#F5F7FA]" />
                  <h3 className="text-sm font-medium text-[#F5F7FA] uppercase tracking-wide">{stage.title}</h3>
                </div>
                <div>
                  <div className="text-xs font-mono text-[#5DA9E9]/70 mb-2 uppercase">{stage.subtitle}</div>
                  <p className="text-sm text-[#AAB4C3] leading-relaxed">{stage.description}</p>
                </div>
              </div>
            );
          })}
        </div>

        {/* Technical Specs Block */}
        <div className="border-t border-white/5 pt-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {TECH_SPECS.map((spec) => (
              <div key={spec.label} className="flex flex-col gap-2">
                <span className="text-[#6E7A8A] text-[10px] font-mono uppercase tracking-widest">
                  {spec.label}
                </span>
                <span className="text-[#F5F7FA] text-sm font-medium">
                  {spec.value}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
