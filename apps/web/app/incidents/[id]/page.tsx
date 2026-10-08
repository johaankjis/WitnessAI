import IncidentDashboard from "./IncidentDashboard";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return {
    title: `Incident ${id} — Witness`,
    description: `Review conflicting driver statements against dashcam evidence for incident ${id}.`,
  };
}

export default async function IncidentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <IncidentDashboard incidentId={id} />;
}
