
'use client';

import { useState, useEffect, useCallback } from 'react';
import { Link } from '@/i18n/navigation';

interface Slide {
  id: number;
  image: string;
  title: string | null;
  subtitle: string | null;
  button_text: string | null;
  url: string;
}

const AUTO_INTERVAL = 5000;

export default function HomepageSlider({ slides }: { slides: Slide[] }) {
  const [current, setCurrent] = useState(0);
  const [paused, setPaused] = useState(false);

  const next = useCallback(() => setCurrent((p) => (p + 1) % slides.length), [slides.length]);
  const prev = useCallback(() => setCurrent((p) => (p - 1 + slides.length) % slides.length), [slides.length]);

  useEffect(() => {
    if (paused || slides.length <= 1) return;
    const id = setInterval(next, AUTO_INTERVAL);
    return () => clearInterval(id);
  }, [paused, slides.length, next]);

  if (slides.length === 0) return null;

  const s = slides[current];

  return (
    <div
      className="relative w-full h-[300px] md:h-[420px] overflow-hidden bg-gray-900"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      {slides.map((slide, i) => (
        <div
          key={slide.id}
          className={'absolute inset-0 transition-opacity duration-700 ' + (i === current ? 'opacity-100' : 'opacity-0 pointer-events-none')}
        >
          <img
            src={slide.image}
            alt={slide.title || ''}
            className="w-full h-full object-cover"
            loading={i === 0 ? 'eager' : 'lazy'}
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-black/20 to-transparent" />
          <div className="absolute bottom-0 left-0 right-0 p-6 md:p-12 text-white">
            {slide.title && <h2 className="text-2xl md:text-4xl font-bold mb-2 drop-shadow-lg">{slide.title}</h2>}
            {slide.subtitle && <p className="text-sm md:text-lg mb-4 max-w-xl text-gray-200 drop-shadow">{slide.subtitle}</p>}
            {slide.button_text && (
              <Link href={slide.url} className="inline-block bg-blue-600 hover:bg-blue-700 text-white px-6 py-2.5 rounded-lg font-semibold text-sm transition">
                {slide.button_text}
              </Link>
            )}
          </div>
        </div>
      ))}

      {/* Arrows */}
      {slides.length > 1 && (
        <>
          <button onClick={prev} className="absolute left-3 top-1/2 -translate-y-1/2 z-10 bg-black/30 hover:bg-black/50 text-white rounded-full w-10 h-10 flex items-center justify-center transition">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" /></svg>
          </button>
          <button onClick={next} className="absolute right-3 top-1/2 -translate-y-1/2 z-10 bg-black/30 hover:bg-black/50 text-white rounded-full w-10 h-10 flex items-center justify-center transition">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" /></svg>
          </button>
        </>
      )}

      {/* Dots */}
      {slides.length > 1 && (
        <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-10 flex gap-2">
          {slides.map((_, i) => (
            <button
              key={i}
              onClick={() => setCurrent(i)}
              className={'w-2.5 h-2.5 rounded-full transition ' + (i === current ? 'bg-white' : 'bg-white/40 hover:bg-white/60')}
            />
          ))}
        </div>
      )}
    </div>
  );
}
