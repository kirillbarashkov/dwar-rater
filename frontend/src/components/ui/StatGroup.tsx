import './StatGroup.css';

interface StatGroupProps {
  title: string;
  stats?: Record<string, string>;
}

export function StatGroup({ title, stats }: StatGroupProps) {
  if (!stats) return null;
  const entries = Object.entries(stats);
  if (entries.length === 0) return null;

  return (
    <div className="stat-group">
      <h3 className="stat-group-title">{title}</h3>
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
  );
}
