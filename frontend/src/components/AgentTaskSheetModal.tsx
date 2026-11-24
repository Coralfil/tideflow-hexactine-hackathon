import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { X, Send, Bot } from 'lucide-react';
import type { ThoughtView } from '../api/client';

interface AgentTaskSheetModalProps {
  thought: ThoughtView;
  onClose: () => void;
  onSubmit: (instructions: string) => Promise<void>;
}

export const AgentTaskSheetModal: React.FC<AgentTaskSheetModalProps> = ({
  thought,
  onClose,
  onSubmit,
}) => {
  const [instructions, setInstructions] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit(instructions);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to submit task to agent');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-overlay">
      <motion.div
        className="modal-content"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 20 }}
      >
        <div className="modal-header">
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Bot size={18} color="#00d9c0" /> Submit to Agent for Completion
          </h3>
          <button type="button" className="btn btn-sm btn-icon" onClick={onClose}>
            <X size={16} />
          </button>
        </div>

        <div className="modal-body">
          <div className="thought-card" style={{ marginBottom: 16 }}>
            <strong>Task: </strong>{thought.text}
          </div>

          <form onSubmit={handleSubmit}>
            <div className="form-group" style={{ marginBottom: 16 }}>
              <label htmlFor="agent_instructions">Custom Instructions / Context</label>
              <textarea
                id="agent_instructions"
                className="input"
                rows={4}
                placeholder="Add any specific requirements, contexts, or answer questions the agent might have..."
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
                style={{ width: '100%', marginTop: '4px', resize: 'vertical' }}
              />
            </div>

            {error && <div className="alert-banner alert-error">{error}</div>}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button type="button" className="btn btn-sm" onClick={onClose}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary btn-sm" disabled={busy}>
                <Send size={14} style={{ marginRight: 4 }} />
                {busy ? 'Submitting...' : 'Send to Worker'}
              </button>
            </div>
          </form>
        </div>
      </motion.div>
    </div>
  );
};
