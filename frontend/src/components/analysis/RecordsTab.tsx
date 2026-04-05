import './RecordsTab.css';

interface RecordsTabProps {
  records: Record<string, string>;
}

export function RecordsTab({ records }: RecordsTabProps) {
  const entries = Object.entries(records);
  if (entries.length === 0) {
    return <p className="tab-placeholder">Рекорды не найдены</p>;
  }

  return (
    <div className="records-tab">
      <div className="stat-group">
        <h3 className="stat-group-title">Боевые рекорды</h3>
        <table className="stat-table">
          <tbody>
            {entries.map(([key, value]) => (
              <tr key={key}>
                <td className="stat-label">{key}</td>
                <td className="stat-value">{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
