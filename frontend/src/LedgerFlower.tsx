// The landing's radial flower geometry, drawn as a small reusable vector.
export default function LedgerFlower({
  className = "",
}: {
  className?: string;
}) {
  return (
    <svg
      className={className}
      viewBox="-60 -60 120 120"
      aria-hidden="true"
      focusable="false"
    >
      <circle r="52" fill="none" stroke="currentColor" strokeWidth="1" />
      {Array.from({ length: 8 }, (_, i) => (
        <g key={i} transform={`rotate(${i * 45})`}>
          <ellipse
            cy="-21"
            rx="11"
            ry="25"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          />
          <circle cy="-52" r="2.5" fill="currentColor" />
        </g>
      ))}
      <circle r="7" fill="currentColor" />
    </svg>
  );
}
