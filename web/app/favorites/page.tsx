import type { Metadata } from "next";
import { Suspense } from "react";
import PaperExplorer from "@/components/PaperExplorer";

export const metadata: Metadata = { title: "我的收藏" };

export default function FavoritesPage() {
  return <Suspense fallback={<main id="main-content" className="loading-message">正在读取收藏…</main>}><PaperExplorer mode="favorites" /></Suspense>;
}
