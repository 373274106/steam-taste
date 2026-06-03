import { useTagLabel } from "../lib/tags";

interface Props {
  data: { tag: string; weight: number }[];
  /** Number of tags to include on the radar. Default 8. */
  top?: number;
  /** SVG side length in viewBox units. Default 400. */
  size?: number;
}

/**
 * Self-implemented SVG radar chart for tag affinity.
 *
 * No chart library — pure SVG so it inherits theme colors via CSS vars
 * and renders crisp at any size. Style notes:
 *  - Concentric guide rings (dashed for inner, solid for outermost).
 *  - 8 axes from center to outer ring.
 *  - Data polygon: amber fill at low opacity + amber stroke + pixel-block
 *    vertices, matching the retro-arcade ornament language.
 *  - Tag labels sit just outside the outer ring, anchored by quadrant.
 *  - Weight readouts below labels in mono tabular small caps.
 */
export default function TagRadar({ data, top = 8, size = 400 }: Props) {
  const label = useTagLabel();
  const items = data.slice(0, top);
  const n = items.length;
  if (n < 3) return null;

  const max = Math.max(...items.map((d) => d.weight), 0.01);

  const center = size / 2;
  const radius = center * 0.62; // leave breathing room for labels
  const labelRadius = radius * 1.18;

  const point = (idx: number, ratio: number) => {
    const angle = (Math.PI * 2 * idx) / n - Math.PI / 2;
    return {
      x: center + Math.cos(angle) * radius * ratio,
      y: center + Math.sin(angle) * radius * ratio,
    };
  };
  const labelPoint = (idx: number) => {
    const angle = (Math.PI * 2 * idx) / n - Math.PI / 2;
    return {
      x: center + Math.cos(angle) * labelRadius,
      y: center + Math.sin(angle) * labelRadius,
    };
  };

  const dataPts = items.map((d, i) => point(i, d.weight / max));
  const dataPath =
    "M " + dataPts.map((p) => `${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(" L ") + " Z";

  const ringRatios = [0.25, 0.5, 0.75, 1.0];
  const rings = ringRatios.map((r) => {
    const pts = items.map((_, i) => point(i, r));
    return (
      "M " + pts.map((p) => `${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(" L ") + " Z"
    );
  });

  const axes = items.map((_, i) => point(i, 1));

  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      className="w-full h-auto"
      role="img"
      aria-label="Tag affinity radar"
    >
      {/* Guide rings */}
      {rings.map((path, i) => (
        <path
          key={`ring-${i}`}
          d={path}
          fill="none"
          stroke="var(--color-border)"
          strokeWidth={i === rings.length - 1 ? 1 : 0.75}
          strokeDasharray={i < rings.length - 1 ? "2 4" : undefined}
        />
      ))}

      {/* Axes */}
      {axes.map((p, i) => (
        <line
          key={`axis-${i}`}
          x1={center}
          y1={center}
          x2={p.x}
          y2={p.y}
          stroke="var(--color-border)"
          strokeWidth={0.5}
        />
      ))}

      {/* Center pixel block */}
      <rect
        x={center - 2}
        y={center - 2}
        width={4}
        height={4}
        fill="var(--color-border-strong)"
      />

      {/* Data shape */}
      <path
        d={dataPath}
        fill="var(--color-accent)"
        fillOpacity={0.18}
        stroke="var(--color-accent)"
        strokeWidth={1.5}
        strokeLinejoin="round"
      />

      {/* Data point pixel-blocks */}
      {dataPts.map((p, i) => (
        <rect
          key={`pt-${i}`}
          x={p.x - 3}
          y={p.y - 3}
          width={6}
          height={6}
          fill="var(--color-accent)"
        />
      ))}

      {/* Labels (tag name + weight) */}
      {items.map((d, i) => {
        const lp = labelPoint(i);
        const dx = lp.x - center;
        const anchor: "start" | "middle" | "end" =
          Math.abs(dx) < 8 ? "middle" : dx > 0 ? "start" : "end";
        // Vertical baseline:
        const dy = lp.y - center;
        const baselineOffset = Math.abs(dy) < 8 ? 0 : dy > 0 ? 12 : -2;
        return (
          <g key={`label-${i}`}>
            <text
              x={lp.x}
              y={lp.y + baselineOffset}
              textAnchor={anchor}
              fill="var(--color-text-hi)"
              style={{
                fontSize: 12,
                fontFamily: "var(--font-body)",
                fontWeight: 500,
                letterSpacing: "0.01em",
              }}
            >
              {label(d.tag)}
            </text>
            <text
              x={lp.x}
              y={lp.y + baselineOffset + 14}
              textAnchor={anchor}
              fill="var(--color-text-dim)"
              style={{
                fontSize: 10,
                fontFamily: "var(--font-mono)",
                fontVariantNumeric: "tabular-nums",
                letterSpacing: "0.05em",
              }}
            >
              {d.weight.toFixed(2)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
