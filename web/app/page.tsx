import { Demo } from "@/components/Demo";
import { aboutText, casesFile, modelCard } from "@/lib/content";

export const dynamic = "force-static";

export default function Page() {
  const card = modelCard();
  return <Demo cases={casesFile()} cardBody={card.body} cardHash={card.hash} about={aboutText()} />;
}
