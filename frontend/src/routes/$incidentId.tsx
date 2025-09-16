import { createFileRoute, useParams } from "@tanstack/react-router"

export const Route = createFileRoute('/$incidentId')({
  component: Incident
})

function Incident() {
  const { incidentId } = useParams({ strict: false })
  return (
    <div>
      <h3>{incidentId}</h3>
      <p>Incident Details</p>
    </div>
  )
}
