import type { Metadata } from "next";
import { Suspense } from "react";
import PaperExplorer from "@/components/PaperExplorer";

export const metadata: Metadata = { title: "最近发表" };

export default function RecentPage() {
  return <Suspense fallback={<main id="main-content" className="loading-message">正在计算最近 7 天的发表…</main>}><PaperExplorer mode="recent" /></Suspense>;
}
