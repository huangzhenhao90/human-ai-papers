import { Suspense } from "react";
import PaperExplorer from "@/components/PaperExplorer";

export default function HomePage() {
  return <Suspense fallback={<main id="main-content" className="loading-message">正在准备统一论文流…</main>}><PaperExplorer mode="all" /></Suspense>;
}
