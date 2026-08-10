import { useEffect, useRef, useState } from 'react';

const STATS = [
    { value: '10x', label: 'Faster Design' },
    { value: '100+', label: 'Models Generated' },
    { value: '24/7', label: 'Available' },
    { value: '<2s', label: 'Latencies' },
];

export function Stats() {
    const [isVisible, setIsVisible] = useState(false);
    const sectionRef = useRef<HTMLElement>(null);

    useEffect(() => {
        const observer = new IntersectionObserver(
            ([entry]) => {
                if (entry.isIntersecting) setIsVisible(true);
            },
            { threshold: 0.2 }
        );
        if (sectionRef.current) observer.observe(sectionRef.current);
        return () => observer.disconnect();
    }, []);

    return (
        <section
            ref={sectionRef}
            className="py-12 border-y border-white/5 bg-[#0D1117] relative z-20"
        >
            <div className="max-w-6xl mx-auto px-6">
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-8 md:gap-12 divide-white/5 divide-x">
                    {STATS.map((stat, idx) => (
                        <div
                            key={idx}
                            className={`flex flex-col items-center justify-center text-center ${idx !== 0 ? 'pl-8 md:pl-12' : ''}`}
                            style={{
                                opacity: isVisible ? 1 : 0,
                                transform: isVisible ? 'translateY(0)' : 'translateY(10px)',
                                transition: `all 0.6s ease ${idx * 0.1}s`
                            }}
                        >
                            <div className="text-3xl md:text-4xl font-serif text-[#F5F7FA] mb-1">
                                {stat.value}
                            </div>
                            <div className="text-xs tracking-widest uppercase font-mono text-[#6E7A8A]">
                                {stat.label}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
}
