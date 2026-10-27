import { Demo } from "@/components/Demo";
import { demoPatients, modelCard } from "@/lib/content";

export const dynamic = "force-static";

export default function Page() {
  const card = modelCard();
  return <Demo patients={demoPatients()} cardBody={card.body} cardHash={card.hash} />;
}
