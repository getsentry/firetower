import { createFileRoute, Link } from "@tanstack/react-router"

export const Route = createFileRoute('/')({
  component: Index
})

function Index() {
  return (
    <div className="p-2">
      <h3>Home page</h3>
      <p>the incidents list will show here</p>
      <Link to="/$incidentId" params={{ incidentId: "INC-1234" }} className="underline">See an incident details page</Link>
    </div>
  )
}
