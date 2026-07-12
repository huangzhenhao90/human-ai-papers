import type { Metadata } from "next";
import Footer from "@/components/Footer";
import HeaderNav from "@/components/HeaderNav";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "AI Papers · 人 × AI 研究索引", template: "%s · AI Papers" },
  description: "追踪 AI 如何改变人、组织与心理健康的跨领域中文论文索引。",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <a href="#main-content" className="skip-link">跳到主要内容</a>
        <HeaderNav />
        <div className="site-frame">{children}</div>
        <Footer />
      </body>
    </html>
  );
}
