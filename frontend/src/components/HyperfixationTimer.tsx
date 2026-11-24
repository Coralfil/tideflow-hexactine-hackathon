import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { BellRing, Timer, XCircle } from 'lucide-react';

interface HyperfixationTimerProps {
  taskId: string;
  taskText: string;
  energyCost: number;
}

export const HyperfixationTimer: React.FC<HyperfixationTimerProps> = ({
  taskId,
  taskText,
  energyCost,
}) => {
  // Base time limit defaults to 25 minutes (Pomodoro standard). 
  // Energy cost modifier: higher energy cost = slightly more time, but still hard capped.
  const baseMinutes = 25 + (energyCost * 5); 
  const totalSeconds = baseMinutes * 60;
  
  const [secondsLeft, setSecondsLeft] = useState(totalSeconds);
  const [isActive, setIsActive] = useState(false);
  const [notified, setNotified] = useState(false);
  
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    // Request notification permissions on mount
    if ('Notification' in window && Notification.permission !== 'granted' && Notification.permission !== 'denied') {
      Notification.requestPermission();
    }
    
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const triggerNotification = () => {
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification('Hyperfixation Alert: Time boundary reached.', {
        body: `You have hit the time limit for: ${taskText}. Please wrap up your current micro-step, park this task, and shift focus to maintain momentum.`,
        icon: '/vite.svg' 
      });
    } else {
      alert(`Hyperfixation Alert! Time boundary reached for: ${taskText}. Wrap up and park this task.`);
    }
  };

  useEffect(() => {
    if (isActive && secondsLeft > 0) {
      timerRef.current = window.setInterval(() => {
        setSecondsLeft(prev => prev - 1);
      }, 1000);
    } else if (isActive && secondsLeft === 0 && !notified) {
      if (timerRef.current) clearInterval(timerRef.current);
      setNotified(true);
      triggerNotification();
      setIsActive(false);
    }

    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
    };
  }, [isActive, secondsLeft, notified, taskText]);

  const toggleTimer = () => {
    setIsActive(!isActive);
  };

  const progressPercent = ((totalSeconds - secondsLeft) / totalSeconds) * 100;
  const isWarning = secondsLeft < 300; // Less than 5 minutes
  
  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <div style={{ marginTop: 12, padding: 8, backgroundColor: '#0f172a', borderRadius: 6, border: '1px solid #1e293b' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: '0.75rem', fontWeight: 600, color: isWarning ? '#f59e0b' : '#38bdf8', display: 'flex', alignItems: 'center', gap: 4 }}>
          <Timer size={12} />
          Anti-Hyperfixation Boundary
        </span>
        <button
          type="button"
          onClick={toggleTimer}
          className={`btn btn-sm ${isActive ? 'btn-danger' : 'btn-primary'}`}
          style={{ padding: '2px 8px', fontSize: '0.7rem' }}
        >
          {isActive ? 'Pause' : (secondsLeft < totalSeconds ? 'Resume' : 'Start Focus')}
        </button>
      </div>
      
      <div className="timer-bar-container">
        <div 
          className={`timer-bar-fill ${isWarning ? 'timer-bar-warning' : ''}`} 
          style={{ width: `${progressPercent}%` }} 
        />
      </div>
      
      <div className="timer-text">
        <span>{formatTime(totalSeconds - secondsLeft)} elapsed</span>
        <span style={{ color: isWarning ? '#ef4444' : 'inherit' }}>{formatTime(secondsLeft)} remaining</span>
      </div>
    </div>
  );
};