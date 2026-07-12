"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { BookmarkIcon, RssIcon } from "@/components/Icons";
import { Spectrum } from "@/components/Spectrum";
import { readFavorites, storageEvents } from "@/lib/storage";

const links = [
  { href: "/", label: "全部论文" },
  { href: "/recent", label: "最近发表" },
  { href: "/favorites", label: "我的收藏", favorite: true },
  { href: "/about", label: "关于" },
];

export default function HeaderNav() {
  const pathname = usePathname();
  const [favoriteCount, setFavoriteCount] = useState(0);

  useEffect(() => {
    const sync = () => setFavoriteCount(readFavorites().size);
    sync();
    window.addEventListener(storageEvents.favorites, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(storageEvents.favorites, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  return (
    <header className="site-header">
      <Spectrum />
      <div className="site-header__inner">
        <Link href="/" className="brand" aria-label="AI Papers 首页">
          <span className="brand__mark" aria-hidden="true"><Spectrum compact /></span>
          <span className="brand__name">AI Papers</span>
          <span className="brand__edition">Human Edition</span>
        </Link>
        <nav className="main-nav" aria-label="主导航">
          {links.map((link) => {
            const active = link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
            return (
              <Link href={link.href} key={link.href} className={active ? "is-active" : ""} aria-current={active ? "page" : undefined}>
                {link.favorite ? <BookmarkIcon className="nav-icon" filled={active} /> : null}
                {link.label}
                {link.favorite && favoriteCount > 0 ? <span className="nav-count">{favoriteCount}</span> : null}
              </Link>
            );
          })}
          <a href="/rss.xml" className="rss-link" aria-label="RSS 订阅"><RssIcon className="nav-icon" />RSS</a>
        </nav>
      </div>
    </header>
  );
}
