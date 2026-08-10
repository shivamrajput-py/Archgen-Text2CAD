import { Cpu, FileCode, Boxes } from 'lucide-react';

const features = [
  {
    icon: Cpu,
    label: 'AI-Powered',
    description: 'Natural language to CAD'
  },
  {
    icon: FileCode,
    label: 'Multi-Format',
    description: 'STL, STEP, OBJ, IGES'
  },
  {
    icon: Boxes,
    label: 'Parametric',
    description: 'Fully editable output'
  },
];

export function FeatureStrip() {
  return (
    <section className="relative py-12 bg-gradient-to-r from-[#0D1117] via-[#11161D] to-[#0D1117] border-y border-white/5">
      <div className="max-w-5xl mx-auto px-6">
        <div className="flex flex-wrap justify-center gap-8 lg:gap-16">
          {features.map((feature, idx) => (
            <div
              key={idx}
              className="flex items-center gap-4 group"
            >
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-[#5DA9E9]/20 to-[#667eea]/20 border border-white/10 flex items-center justify-center group-hover:border-[#5DA9E9]/50 transition-all duration-300">
                <feature.icon size={24} className="text-[#5DA9E9] group-hover:scale-110 transition-transform" />
              </div>
              <div>
                <p className="text-[#F5F7FA] font-medium text-sm">{feature.label}</p>
                <p className="text-[#6E7A8A] text-xs">{feature.description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
