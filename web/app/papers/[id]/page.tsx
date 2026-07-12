import type { Metadata } from "next";
import PaperDetailView from "@/components/PaperDetailView";

export const metadata: Metadata = { title: "论文详情" };

export default function PaperPage() {
  return <PaperDetailView />;
}
