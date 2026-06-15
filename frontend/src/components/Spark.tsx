/**
 * Spark — the Anthropic-style asterisk mark used as the agent's model icon and
 * floating "thinking" indicator. Static when idle; when the agent is thinking or
 * working it breathes, drifts and emits a soft copper glow — the literal animated
 * version of the spark PNG, rendered crisply via CSS (no gimmick, just presence).
 */
interface SparkProps {
  size?: number;
  state?: 'idle' | 'thinking' | 'working';
  tone?: 'copper' | 'ink' | 'white';
  className?: string;
}

const SRC: Record<string, string> = {
  copper: '/spark.png',
  ink: '/spark-ink.png',
  white: '/spark-white.png',
};

export default function Spark({ size = 16, state = 'idle', tone = 'copper', className = '' }: SparkProps) {
  return (
    <span
      className={`spark ${state !== 'idle' ? state : ''} ${className}`}
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      <img src={SRC[tone]} alt="" className="spark-img" draggable={false} />
    </span>
  );
}
