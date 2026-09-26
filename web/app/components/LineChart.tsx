type Series = { label: string; color: string; values: number[]; dashed?: boolean };

export default function LineChart({ labels, series, title, height = 240 }: {
  labels: string[]; series: Series[]; title: string; height?: number;
}) {
  const W = 720, H = height, pad = { l: 44, r: 12, t: 28, b: 26 };
  const all = series.flatMap((s) => s.values);
  const min = Math.min(0, ...all), max = Math.max(1, ...all);
  const x = (i: number) => pad.l + (labels.length <= 1 ? 0 : (i / (labels.length - 1)) * (W - pad.l - pad.r));
  const y = (v: number) => pad.t + (1 - (v - min) / (max - min || 1)) * (H - pad.t - pad.b);
  const ticks = [min, (min + max) / 2, max];
  return (
    <div className="chart">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={title}>
        <text x={pad.l} y={16} fill="#e8edf6" fontSize="13" fontWeight="600">{title}</text>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} stroke="#1f2738" />
            <text x={pad.l - 6} y={y(t) + 4} fill="#8a96ab" fontSize="11" textAnchor="end">{Math.round(t)}</text>
          </g>
        ))}
        {min < 0 && <line x1={pad.l} x2={W - pad.r} y1={y(0)} y2={y(0)} stroke="#3a4560" />}
        {labels.map((l, i) => (labels.length < 20 || i % 2 === 0) && (
          <text key={l} x={x(i)} y={H - 8} fill="#8a96ab" fontSize="11" textAnchor="middle">{l}</text>
        ))}
        {series.map((s) => (
          <polyline key={s.label} fill="none" stroke={s.color} strokeWidth={s.dashed ? 1.5 : 3}
                    strokeDasharray={s.dashed ? "5 5" : undefined} strokeLinejoin="round"
                    points={s.values.map((v, i) => `${x(i)},${y(v)}`).join(" ")} />
        ))}
      </svg>
      <div className="legend">
        {series.map((s) => <span key={s.label}><i style={{ background: s.color }} />{s.label}</span>)}
      </div>
    </div>
  );
}
