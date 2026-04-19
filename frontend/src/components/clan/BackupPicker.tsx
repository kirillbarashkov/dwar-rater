import { useState, useEffect, useCallback } from 'react';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { LoadingSpinner } from '../ui/LoadingSpinner';
import { listTreasuryBackups, saveTreasuryBackup, restoreTreasuryBackup, getTreasuryBackup, type BackupFile, type TreasuryExportData } from '../../api/clanInfo';
import './BackupPicker.css';

interface BackupPickerProps {
  isOpen: boolean;
  onClose: () => void;
  clanId: number;
  mode: 'save' | 'restore';
  onSuccess?: (message: string) => void;
}

export function BackupPicker({ isOpen, onClose, clanId, mode, onSuccess }: BackupPickerProps) {
  const [backups, setBackups] = useState<BackupFile[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [selectedFile, setSelectedFile] = useState<BackupFile | null>(null);
  const [previewData, setPreviewData] = useState<TreasuryExportData | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadBackups = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listTreasuryBackups(clanId);
      setBackups(data.backups);
    } catch {
      setError('Не удалось загрузить список бэкапов');
    } finally {
      setIsLoading(false);
    }
  }, [clanId]);

  useEffect(() => {
    if (!isOpen || mode !== 'restore') {
      setIsLoading(false);
      return;
    }
    loadBackups();
  }, [isOpen, mode, clanId, loadBackups]);

  const handleSave = async () => {
    setIsProcessing(true);
    setError(null);
    try {
      const result = await saveTreasuryBackup(clanId);
      onSuccess?.(result.message);
      onClose();
    } catch {
      setError('Не удалось сохранить бэкап');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSelectFile = async (backup: BackupFile) => {
    setSelectedFile(backup);
    setIsProcessing(true);
    try {
      const data = await getTreasuryBackup(clanId, backup.filename);
      setPreviewData(data);
    } catch {
      setError('Не удалось загрузить превью');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleRestore = async () => {
    if (!selectedFile) return;
    setIsProcessing(true);
    setError(null);
    try {
      const result = await restoreTreasuryBackup(clanId, selectedFile.filename);
      onSuccess?.(result.message);
      onClose();
    } catch {
      setError('Не удалось восстановить бэкап');
    } finally {
      setIsProcessing(false);
    }
  };

  const formatSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (isoString: string): string => {
    return new Date(isoString).toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatFilename = (filename: string): string => {
    const match = filename.match(/treasury-\d+-(\d{8})-(\d{6})\.json/);
    if (!match) return filename;
    const [date, time] = match;
    const formattedDate = `${date.slice(-14, -8)}-${date.slice(-8, -6)}.${date.slice(-6, -4)}.${date.slice(-4, -2)}`;
    const formattedTime = `${time.slice(0, 2)}:${time.slice(2, 4)}:${time.slice(4, 6)}`;
    return `${formattedDate} ${formattedTime}`;
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={mode === 'save' ? 'Создать резервную копию' : 'Восстановить из резервной копии'}
      wide
    >
      <div className="backup-picker">
        {error && <div className="backup-error">{error}</div>}

        {mode === 'save' ? (
          <div className="backup-save">
            <p className="backup-description">
              Будет создана резервная копия всех операций казны текущего клана.
              Файл будет сохранён на сервере в папке <code>backup</code>.
            </p>
            <div className="backup-actions">
              <Button variant="primary" onClick={handleSave} disabled={isProcessing}>
                {isProcessing ? 'Сохранение...' : 'Создать резервную копию'}
              </Button>
              <Button variant="ghost" onClick={onClose}>
                Отмена
              </Button>
            </div>
          </div>
        ) : (
          <div className="backup-restore">
            {isLoading ? (
              <LoadingSpinner />
            ) : backups.length === 0 ? (
              <div className="backup-empty">
                <p>Нет доступных резервных копий</p>
                <p className="backup-empty-hint">Сначала создайте резервную копию с помощью кнопки &quot;Экспорт&quot;</p>
              </div>
            ) : (
              <>
                <div className="backup-list">
                  <div className="backup-list-header">
                    <span>Файл</span>
                    <span>Размер</span>
                    <span>Дата</span>
                  </div>
                  <div className="backup-list-body">
                    {backups.map((backup) => (
                      <div
                        key={backup.filename}
                        className={`backup-item ${selectedFile?.filename === backup.filename ? 'selected' : ''}`}
                        onClick={() => handleSelectFile(backup)}
                      >
                        <span className="backup-filename">{formatFilename(backup.filename)}</span>
                        <span className="backup-size">{formatSize(backup.size)}</span>
                        <span className="backup-date">{formatDate(backup.modified)}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {selectedFile && (
                  <div className="backup-preview">
                    <h4>Предпросмотр:</h4>
                    {isProcessing ? (
                      <LoadingSpinner />
                    ) : previewData ? (
                      <>
                        <pre className="backup-preview-json">
                          {JSON.stringify(previewData.operations.slice(0, 3), null, 2)}
                        </pre>
                        <p className="backup-preview-hint">
                          Всего операций: {previewData.operations_count}
                        </p>
                      </>
                    ) : null}
                  </div>
                )}

                <div className="backup-actions">
                  <Button
                    variant="danger"
                    onClick={handleRestore}
                    disabled={!selectedFile || isProcessing}
                  >
                    {isProcessing ? 'Восстановление...' : 'Восстановить'}
                  </Button>
                  <Button variant="ghost" onClick={onClose}>
                    Отмена
                  </Button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
}
