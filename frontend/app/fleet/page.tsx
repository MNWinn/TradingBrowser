import { AgentFleetVisualizer } from '@/components/agents'

export default function AgentFleetPage() {
  return (
    <div className="container mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">Agent Fleet Status</h1>
      <AgentFleetVisualizer />
    </div>
  )
}
