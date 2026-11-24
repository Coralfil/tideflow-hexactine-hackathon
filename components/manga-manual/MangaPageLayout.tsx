import React from 'react';
import { motion, type HTMLMotionProps } from 'framer-motion';

export interface MangaPageLayoutProps {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  issue?: string | number;
  volume?: string | number;
  chapter?: string | number;
  pageNumber?: string | number;
  classification?: string;
  className?: string;
}

export interface MangaPanelProps extends HTMLMotionProps<'div'> {
  children: React.ReactNode;
  colSpan?: string;
  title?: string;
  actionBadge?: string;
  screentone?: boolean | 'dense' | 'light' | 'lines' | 'cyan';
  soundFx?: string;
  className?: string;
}

export interface MangaSpeechBubbleProps {
  speaker?: string;
  children: React.ReactNode;
  variant?: 'normal' | 'shout' | 'system';
  className?: string;
}

/**
 * MangaPageLayout Component
 * Recreates the authentic structural layout of a printed manga page,
 * including heavy ink borders, paper newsprint tone, halftone rasters,
 * and Framer Motion interactive hover dynamics.
 */
export const MangaPageLayout: React.FC<MangaPageLayoutProps> = ({
  children,
  title = 'AGENTSEA SPECIFICATION MANUAL',
  subtitle = 'HEXACTINE LATTICE ARCHITECTURAL DIRECTIVE',
  issue = '01',
  volume = '1',
  chapter = '04',
  pageNumber = '27',
  classification = 'STRICTLY CLASSIFIED (BENTHIC INTEL)',
  className = '',
}) => {
  return (
    <div
      className={`max-w-6xl mx-auto bg-[#F4F1EA] text-[#111111] p-4 sm:p-6 md:p-8 border-4 border-black relative overflow-hidden shadow-[12px_12px_0px_0px_rgba(0,0,0,1)] ${className}`}
      style={{
        backgroundImage: 'radial-gradient(rgba(0, 0, 0, 0.05) 1px, transparent 1px)',
        backgroundSize: '12px 12px',
      }}
    >
      {/* Halftone dot pattern overlay for authentic manga feel */}
      <div
        className="absolute inset-0 pointer-events-none opacity-10"
        style={{
          backgroundImage: 'radial-gradient(#000 1.5px, transparent 1.5px)',
          backgroundSize: '6px 6px',
        }}
        aria-hidden="true"
      />

      {/* Manga Page Running Header */}
      <header className="relative z-10 border-b-4 border-black pb-3 mb-6 flex flex-wrap items-center justify-between gap-3 bg-white p-3 border-2 border-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)]">
        <div className="flex items-center gap-3">
          <span className="bg-black text-white px-2.5 py-1 text-xs font-black uppercase tracking-wider -skew-x-6 inline-block">
            VOL. {volume} // ISSUE #{issue}
          </span>
          <div>
            <h1 className="text-xl sm:text-2xl font-black uppercase tracking-tight italic m-0 leading-tight">
              {title}
            </h1>
            <p className="text-xs font-bold uppercase tracking-wider text-gray-600 m-0">
              {subtitle} | CHAPTER {chapter}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[10px] font-black uppercase tracking-widest px-2 py-1 bg-yellow-300 border-2 border-black shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
            READING: LEFT TO RIGHT
          </span>
          <span className="text-[10px] font-black uppercase tracking-widest px-2 py-1 bg-red-500 text-white border-2 border-black shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
            {classification}
          </span>
        </div>
      </header>

      {/* Manga Grid (12-column structural paneling) */}
      <main className="relative z-10 grid grid-cols-1 md:grid-cols-12 gap-5">
        {children}
      </main>

      {/* Manga Page Running Footer */}
      <footer className="relative z-10 border-t-4 border-black pt-3 mt-6 flex flex-wrap items-center justify-between gap-2 text-xs font-black uppercase tracking-wider text-gray-700">
        <div className="flex items-center gap-4">
          <span className="font-mono bg-black text-white px-2 py-0.5 text-[11px]">
            CORALFIL-OS // HEXACTINE-LATTICE
          </span>
          <span className="hidden sm:inline text-gray-500">
            SYSTEM INVARIANT: MAX DEGREE = 6
          </span>
        </div>

        <div className="flex items-center gap-3 font-mono">
          <span className="text-gray-500">
            BARCODE: 978-0-HEXACTINE-7B
          </span>
          <span className="bg-white border-2 border-black px-2 py-0.5 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)]">
            PAGE {pageNumber}
          </span>
        </div>
      </footer>
    </div>
  );
};

/**
 * MangaPanel Component
 * An individual story or metric panel with authentic comic ink borders,
 * hard offset drop-shadow, and Framer Motion lift effect on hover.
 */
export const MangaPanel: React.FC<MangaPanelProps> = ({
  children,
  colSpan = 'col-span-12',
  title,
  actionBadge,
  screentone,
  soundFx,
  className = '',
  ...motionProps
}) => {
  const getScreentoneClass = () => {
    if (!screentone) return '';
    if (screentone === 'dense') return 'screentone-dense';
    if (screentone === 'light') return 'screentone-light';
    if (screentone === 'lines') return 'screentone-lines';
    if (screentone === 'cyan') return 'screentone-cyan';
    return 'screentone-bg';
  };

  return (
    <motion.div
      className={`${colSpan} border-4 border-black bg-white p-5 sm:p-6 shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] relative transition-shadow duration-200 hover:shadow-[10px_10px_0px_0px_rgba(0,0,0,1)] ${getScreentoneClass()} ${className}`}
      whileHover={{ scale: 1.01, x: -2, y: -2 }}
      transition={{ type: 'spring', stiffness: 400, damping: 25 }}
      {...motionProps}
    >
      {/* Sound Effect Typography Sticker */}
      {soundFx && (
        <span
          className="absolute -top-3 -right-2 bg-yellow-300 text-black px-2 py-0.5 text-xs font-black italic tracking-tighter uppercase border-2 border-black shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] transform rotate-6 z-20 pointer-events-none select-none"
        >
          *{soundFx}*
        </span>
      )}

      {/* Optional Panel Header with Action Badge */}
      {(title || actionBadge) && (
        <div className="flex items-center justify-between border-b-2 border-black pb-3 mb-4 gap-2">
          {title && (
            <h3 className="text-lg sm:text-xl font-black uppercase tracking-tight italic m-0">
              {title}
            </h3>
          )}
          {actionBadge && (
            <span className="bg-black text-white text-[11px] font-black uppercase tracking-widest px-2 py-0.5 -skew-x-6">
              {actionBadge}
            </span>
          )}
        </div>
      )}

      {children}
    </motion.div>
  );
};

/**
 * MangaSpeechBubble Component
 * Renders dialogue or system commentary inside a comic book bubble.
 */
export const MangaSpeechBubble: React.FC<MangaSpeechBubbleProps> = ({
  speaker,
  children,
  variant = 'normal',
  className = '',
}) => {
  if (variant === 'shout') {
    return (
      <div className={`relative bg-white border-4 border-black p-4 shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] my-2 ${className}`}>
        {speaker && (
          <div className="text-xs font-black uppercase tracking-wider text-red-600 mb-1">
            [{speaker} EXCLAIMS]:
          </div>
        )}
        <div className="text-sm font-black italic tracking-tight uppercase leading-snug">
          {children}
        </div>
      </div>
    );
  }

  return (
    <div className={`relative bg-white border-3 border-black rounded-2xl p-4 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] my-2 ${className}`}>
      {speaker && (
        <div className="text-xs font-black uppercase tracking-wider text-gray-600 mb-1">
          {speaker}
        </div>
      )}
      <div className="text-sm font-semibold leading-relaxed">
        {children}
      </div>
    </div>
  );
};
