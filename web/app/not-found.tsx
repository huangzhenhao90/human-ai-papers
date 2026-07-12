import Link from "next/link";

export default function NotFound() {
  return <main id="main-content" className="state-page"><span className="state-page__code">404 / NOT FOUND</span><h1>这个页面不在论文索引里</h1><p>可以返回统一论文流，继续搜索三个研究领域。</p><Link href="/">返回全部论文</Link></main>;
}
