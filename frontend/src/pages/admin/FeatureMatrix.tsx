import { useState, useEffect, useCallback } from 'react';
import apiClient from '../../api/client';

interface FeatureAction {
  action: string;
  label: string;
  description: string;
}

interface Feature {
  feature: string;
  actions: FeatureAction[];
}

export function FeatureMatrix() {
  const [features, setFeatures] = useState<Feature[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const res = await apiClient.get('/api/admin/features');
      setFeatures(res.data.features);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) return <div className="admin-loading">Загрузка...</div>;

  return (
    <div className="feature-matrix">
      <h2>Матрица фич (справочник)</h2>
      <p className="feature-matrix-desc">
        Полный список всех фич и действий, зарегистрированных в системе.
        Используется для настройки прав доступа на вкладке «Роли и права».
      </p>

      {features.map((f) => (
        <div key={f.feature} className="feature-group">
          <h3 className="feature-group-title">{f.feature}</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Действие</th>
                <th>Название</th>
                <th>Описание</th>
              </tr>
            </thead>
            <tbody>
              {f.actions.map((a) => (
                <tr key={a.action}>
                  <td><code>{a.action}</code></td>
                  <td>{a.label}</td>
                  <td>{a.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}
