"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type MouseEvent } from "react";
import { BookmarkIcon, RssIcon } from "@/components/Icons";
import { Spectrum } from "@/components/Spectrum";
import { readFavorites, storageEvents } from "@/lib/storage";

const links = [
  { href: "/", label: "全部论文" },
  { href: "/recent", label: "最近发表" },
  { href: "/favorites", label: "我的收藏", favorite: true },
  { href: "/about", label: "关于" },
];
const explorerPaths = new Set(["/", "/recent", "/favorites"]);
const explorerNavigateEvent = "ai-papers:explorer-navigate";

export default function HeaderNav() {
  const pathname = usePathname();
  const [displayPath, setDisplayPath] = useState(pathname);
  const [favoriteCount, setFavoriteCount] = useState(0);

  useEffect(() => {
    if (typeof window !== "undefined" && pathname !== window.location.pathname) return;
    setDisplayPath(pathname);
  }, [pathname]);

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

  useEffect(() => {
    const syncPath = () => setDisplayPath(window.location.pathname);
    window.addEventListener("popstate", syncPath);
    window.addEventListener(explorerNavigateEvent, syncPath);
    return () => {
      window.removeEventListener("popstate", syncPath);
      window.removeEventListener(explorerNavigateEvent, syncPath);
    };
  }, []);

  function navigateWithinExplorer(event: MouseEvent<HTMLAnchorElement>, href: string) {
    if (!explorerPaths.has(displayPath) || !explorerPaths.has(href) || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    if (displayPath === href) return;
    History.prototype.pushState.call(window.history, null, "", href);
    window.dispatchEvent(new CustomEvent(explorerNavigateEvent));
    window.scrollTo({ top: 0 });
  }

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
            const active = link.href === "/" ? displayPath === "/" : displayPath.startsWith(link.href);
            const instant = explorerPaths.has(displayPath) && explorerPaths.has(link.href);
            const label = (
              <>
                {link.favorite ? <BookmarkIcon className="nav-icon" filled={active} /> : null}
                {link.label}
                {link.favorite && favoriteCount > 0 ? <span className="nav-count">{favoriteCount}</span> : null}
              </>
            );
            if (instant) return <a href={link.href} onClick={(event) => navigateWithinExplorer(event, link.href)} key={link.href} className={active ? "is-active" : ""} aria-current={active ? "page" : undefined}>{label}</a>;
            return <Link href={link.href} key={link.href} className={active ? "is-active" : ""} aria-current={active ? "page" : undefined}>{label}</Link>;
          })}
          <a href="/rss.xml" className="rss-link" aria-label="RSS 订阅"><RssIcon className="nav-icon" />RSS</a>
        </nav>
      </div>
    </header>
  );
}
