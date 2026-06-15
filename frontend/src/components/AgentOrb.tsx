/**
 * AgentOrb is kept as a thin alias over <Spark> so every existing call site now
 * renders the asterisk spark mark (and animates while thinking/working).
 */
import Spark from './Spark';

interface AgentOrbProps {
  size?: number;
  state?: 'idle' | 'thinking' | 'working';
  className?: string;
}

export default function AgentOrb({ size = 16, state = 'idle', className = '' }: AgentOrbProps) {
  return <Spark size={size} state={state} className={className} />;
}
