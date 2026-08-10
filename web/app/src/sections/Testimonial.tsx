import { useState } from 'react';
import { Quote } from 'lucide-react';

const testimonials = [
  {
    quote: 'Archgen bridges the gap between vision and engineering reality.',
    author: 'Lead Structural Engineer',
    company: 'ARCH X',
  },
  {
    quote: 'The parametric control has transformed how we approach early-stage design.',
    author: 'Principal Architect',
    company: 'Studio Forma',
  },
  {
    quote: 'Finally, a tool that speaks the language of structural intent.',
    author: 'Infrastructure Director',
    company: 'Metro Systems',
  },
];

export function Testimonial() {
  const [activeIndex, setActiveIndex] = useState(0);

  return (
    <section className="relative w-full py-20 lg:py-28 bg-[#0D1117]">
      {/* Top border */}
      <div className="absolute top-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />
      
      <div className="w-full px-6 lg:px-12 xl:px-16">
        <div className="max-w-3xl mx-auto text-center">
          {/* Quote Icon */}
          <div className="mb-8">
            <Quote 
              className="w-8 h-8 text-[#5DA9E9]/40 mx-auto" 
              strokeWidth={1.5}
              fill="currentColor"
            />
          </div>
          
          {/* Quote Text */}
          <blockquote className="heading-serif text-2xl sm:text-3xl lg:text-4xl text-[#F5F7FA] mb-8 leading-snug">
            "{testimonials[activeIndex].quote}"
          </blockquote>
          
          {/* Attribution */}
          <div className="text-[#6E7A8A] text-sm">
            <span className="text-[#AAB4C3]">— {testimonials[activeIndex].author}</span>
            <span className="mx-2">·</span>
            <span>{testimonials[activeIndex].company}</span>
          </div>
          
          {/* Dot Indicators */}
          <div className="flex justify-center gap-2 mt-10">
            {testimonials.map((_, index) => (
              <button
                key={index}
                onClick={() => setActiveIndex(index)}
                className={`w-2 h-2 rounded-full transition-all duration-300 ${
                  index === activeIndex
                    ? 'bg-[#5DA9E9] w-4'
                    : 'bg-white/20 hover:bg-white/30'
                }`}
                aria-label={`Go to testimonial ${index + 1}`}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
