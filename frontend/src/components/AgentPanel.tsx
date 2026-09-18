import React, { useState } from 'react';
import type { AgentQueryResponse, EvidenceItem } from '../api/types';
import { 
  SparklesIcon, 
  SearchIcon, 
  ShieldCheckIcon, 
  ChevronDownIcon, 
  ChevronUpIcon,
  MailIcon,
  MicIcon,
  UsersIcon,
  CalendarIcon
} from './Icons';

interface AgentPanelProps {
  onQuery: (query: string) => void;
  isLoading: boolean;
  response: AgentQueryResponse | null;
  error?: string | null;
}

const QUICK_PROMPTS = [
  'What did I promise Raghav?',
  'What needs action today?',
  'Who owns the Mumbai lease?',
  'What are my meetings today?',
  'What is waiting on others?',
];

export const AgentPanel: React.FC<AgentPanelProps> = ({
  onQuery,
  isLoading,
  response,
  error,
}) => {
  const [inputText, setInputText] = useState('');
  const [evidenceOpen, setEvidenceOpen] = useState(true);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputText.trim() && !isLoading) {
      onQuery(inputText.trim());
    }
  };

  const handleChipClick = (prompt: string) => {
    setInputText(prompt);
    onQuery(prompt);
  };

  const getSourceIcon = (sourceType: string) => {
    switch (sourceType?.toUpperCase()) {
      case 'EMAIL':
        return <MailIcon size={14} />;
      case 'VOICE_NOTE':
        return <MicIcon size={14} />;
      case 'MEETING':
      case 'TRANSCRIPT':
        return <UsersIcon size={14} />;
      case 'CALENDAR':
        return <CalendarIcon size={14} />;
      default:
        return <ShieldCheckIcon size={14} />;
    }
  };

  const evidenceCount = response?.evidence?.length || 0;

  return (
    <section className="agent-panel" id="executive-agent">
      <div className="agent-header-row">
        <div className="agent-title-lockup">
          <span className="agent-icon-sparkle">
            <SparklesIcon size={18} />
          </span>
          <div>
            <h2 className="agent-title">NATURAL LANGUAGE AGENT</h2>
            <p className="agent-subtitle">
              Ask questions grounded strictly in the AIONOS assessment data pack
            </p>
          </div>
        </div>
      </div>

      {/* Quick Prompt Chips */}
      <div className="prompt-chips-wrapper">
        <span className="chips-label">Suggested Inquiries:</span>
        <div className="prompt-chips-list">
          {QUICK_PROMPTS.map((prompt) => (
            <button
              key={prompt}
              type="button"
              className="prompt-chip"
              disabled={isLoading}
              onClick={() => handleChipClick(prompt)}
            >
              {prompt}
            </button>
          ))}
        </div>
      </div>

      {/* Search Input Bar */}
      <form onSubmit={handleSubmit} className="agent-input-form">
        <div className="input-group">
          <span className="input-search-icon">
            <SearchIcon size={18} />
          </span>
          <input
            type="text"
            className="agent-text-input"
            placeholder="Ask anything (e.g. 'What did I promise Raghav?')..."
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            disabled={isLoading}
          />
          <button
            type="submit"
            className="agent-submit-btn"
            disabled={isLoading || !inputText.trim()}
          >
            {isLoading ? (
              <span className="btn-spinner" />
            ) : (
              <span>Ask Agent</span>
            )}
          </button>
        </div>
      </form>

      {/* Error state */}
      {error && (
        <div className="agent-error-banner">
          <span>{error}</span>
        </div>
      )}

      {/* Agent Response Card */}
      {response && (
        <div className="agent-response-container">
          <div className="response-header-bar">
            <div className="response-query-meta">
              <span className="query-label">Question:</span>
              <span className="query-text">"{response.query}"</span>
            </div>

            {/* Trust badge */}
            <div className="trust-badge">
              <ShieldCheckIcon size={14} />
              <span>
                SOURCE-BACKED — Grounded in {evidenceCount}{' '}
                {evidenceCount === 1 ? 'record' : 'records'}
              </span>
            </div>
          </div>

          <div className="response-body">
            {response.answer.split('\n\n').map((paragraph, idx) => (
              <p key={idx} className="response-paragraph">
                {paragraph}
              </p>
            ))}
          </div>

          {/* Collapsible Evidence Citations */}
          {response.evidence && response.evidence.length > 0 && (
            <div className="citations-wrapper">
              <button
                type="button"
                className="citations-toggle-btn"
                onClick={() => setEvidenceOpen(!evidenceOpen)}
              >
                <div className="citations-toggle-left">
                  <ShieldCheckIcon size={14} />
                  <span>
                    Verified Source Citations ({response.evidence.length})
                  </span>
                </div>
                {evidenceOpen ? (
                  <ChevronUpIcon size={14} />
                ) : (
                  <ChevronDownIcon size={14} />
                )}
              </button>

              {evidenceOpen && (
                <div className="citations-list">
                  {response.evidence.map((ev: EvidenceItem, idx: number) => (
                    <div key={`${ev.source_id}-${idx}`} className="citation-card">
                      <div className="citation-top">
                        <span className="source-type-tag">
                          {getSourceIcon(ev.source_type)}
                          {ev.source_type}
                        </span>
                        <span className="citation-title">
                          {ev.source_reference || ev.source_id}
                        </span>
                        {ev.occurred_at && (
                          <span className="citation-date">
                            {new Date(ev.occurred_at).toLocaleString(
                              undefined,
                              {
                                month: 'short',
                                day: 'numeric',
                                hour: '2-digit',
                                minute: '2-digit',
                              }
                            )}
                          </span>
                        )}
                      </div>
                      {ev.evidence_text && (
                        <blockquote className="citation-excerpt">
                          "{ev.evidence_text}"
                        </blockquote>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
};
