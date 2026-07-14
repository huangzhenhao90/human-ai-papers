import Link from "next/link";
import { RssIcon } from "@/components/Icons";
import { Spectrum } from "@/components/Spectrum";

export default function Footer() {
  return (
    <footer className="site-footer">
      <Spectrum />
      <div className="site-footer__inner">
        <div><strong>AI Papers</strong><p>让分散的人 × AI 研究，在一条清晰的论文流里相遇。</p></div>
        <nav aria-label="页脚导航"><Link href="/" prefetch={false}>全部论文</Link><Link href="/recent" prefetch={false}>最近发表</Link><Link href="/favorites" prefetch={false}>我的收藏</Link><Link href="/about" prefetch={false}>关于</Link><a href="/rss.xml"><RssIcon />RSS</a></nav>
      </div>
    </footer>
  );
}
