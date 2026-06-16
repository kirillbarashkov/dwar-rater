import { useState, useEffect, useCallback } from 'react';
import './DeployModal.css';

interface DeployModalProps {
  onClose: () => void;
  currentVersion: string;
}

interface ChangelogEntry {
  sha: string;
  message: string;
  author: string;
  date: string;
}

type DeployStatus = 'idle' | 'creating_pr' | 'pr_created' | 'deploying' | 'success' | 'error';

export function DeployModal({ onClose, currentVersion }: DeployModalProps) {
  const [status, setStatus] = useState<DeployStatus>('idle');
  const [bumpPart, setBumpPart] = useState<'patch' | 'minor' | 'major'>('patch');
  const [changelog, setChangelog] = useState<ChangelogEntry[]>([]);
  const [prUrl, setPrUrl] = useState<string>('');
  const [newVersion, setNewVersion] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [deployStatus, setDeployStatus] = useState<string>('');

  const checkDeployStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/admin/deploy/status');
      const data = await res.json();
      setDeployStatus(data.status || '');
      if (data.status === 'completed' && data.conclusion === 'success') {
        setStatus('success');
      }
    } catch {
      // Ignore polling errors
    }
  }, []);

  useEffect(() => {
    if (status === 'deploying') {
      const interval = setInterval(checkDeployStatus, 5000);
      return () => clearInterval(interval);
    }
  }, [status, checkDeployStatus]);

  const handleDeploy = async () => {
    setStatus('creating_pr');
    setErrorMessage('');

    try {
      const res = await fetch('/api/admin/deploy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bump_part: bumpPart }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || 'Deploy failed');
      }

      setNewVersion(data.version);
      setChangelog(data.changelog || []);

      if (data.status === 'pr_created') {
        setPrUrl(data.pr_url);
        setStatus('pr_created');
      } else if (data.status === 'pr_exists') {
        setStatus('error');
        setErrorMessage('PR dev→main already exists. Merge it first or close it.');
      }
    } catch (err: any) {
      setStatus('error');
      setErrorMessage(err.message || 'Unknown error');
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="deploy-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>⚡ Deploy to Production</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body">
          <div className="version-bump-section">
            <label className="section-label">Version bump:</label>
            <div className="bump-options">
              {(['patch', 'minor', 'major'] as const).map(part => (
                <button
                  key={part}
                  className={`bump-btn ${bumpPart === part ? 'active' : ''}`}
                  onClick={() => setBumpPart(part)}
                  disabled={status !== 'idle'}
                >
                  {part}
                </button>
              ))}
            </div>
            <p className="version-preview">
              Current: <strong>v{currentVersion}</strong>
            </p>
          </div>

          {status === 'idle' && (
            <button className="deploy-btn" onClick={handleDeploy}>
              Create PR & Deploy
            </button>
          )}

          {status === 'creating_pr' && (
            <div className="status-message">
              <div className="spinner" />
              <p>Creating PR dev→main...</p>
            </div>
          )}

          {status === 'pr_created' && (
            <div className="status-message success">
              <p>✅ PR #{newVersion} created successfully!</p>
              <a href={prUrl} target="_blank" rel="noopener noreferrer" className="pr-link">
                View PR →
              </a>
              <p className="deploying-hint">
                CI/CD will auto-deploy after merge. Polling status...
              </p>
              {deployStatus && <p className="ci-status">CI: <strong>{deployStatus}</strong></p>}
            </div>
          )}

          {status === 'success' && (
            <div className="status-message success">
              <p>🚀 Deployed v{newVersion} to production!</p>
              <button className="reload-btn" onClick={() => window.location.reload()}>
                Reload page
              </button>
            </div>
          )}

          {status === 'error' && (
            <div className="status-message error">
              <p>❌ {errorMessage}</p>
              <button className="retry-btn" onClick={() => setStatus('idle')}>
                Try again
              </button>
            </div>
          )}

          {changelog.length > 0 && (
            <div className="changelog-section">
              <h3>Changes ({changelog.length})</h3>
              <ul className="changelog-list">
                {changelog.map((entry, i) => (
                  <li key={i} className="changelog-item">
                    <span className="commit-sha">{entry.sha}</span>
                    <span className="commit-msg">{entry.message}</span>
                    <span className="commit-meta">
                      {entry.author} · {formatDate(entry.date)}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
