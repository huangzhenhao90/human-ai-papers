import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function IconBase({ children, ...props }: IconProps) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{children}</svg>;
}

export function SearchIcon(props: IconProps) {
  return <IconBase {...props}><circle cx="11" cy="11" r="6.5" /><path d="m16 16 4 4" /></IconBase>;
}

export function FilterIcon(props: IconProps) {
  return <IconBase {...props}><path d="M4 6h16M7 12h10M10 18h4" /></IconBase>;
}

export function BookmarkIcon({ filled, ...props }: IconProps & { filled?: boolean }) {
  return <svg viewBox="0 0 24 24" fill={filled ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}><path d="M6.5 4.5a2 2 0 0 1 2-2h7a2 2 0 0 1 2 2v17L12 18l-5.5 3.5z" /></svg>;
}

export function ArrowIcon(props: IconProps) {
  return <IconBase {...props}><path d="M5 12h14M14 7l5 5-5 5" /></IconBase>;
}

export function CloseIcon(props: IconProps) {
  return <IconBase {...props}><path d="m6 6 12 12M18 6 6 18" /></IconBase>;
}

export function RefreshIcon(props: IconProps) {
  return <IconBase {...props}><path d="M20 6v5h-5M4 18v-5h5" /><path d="M18.2 9A7 7 0 0 0 6 6.7L4 11M5.8 15A7 7 0 0 0 18 17.3l2-4.3" /></IconBase>;
}

export function RssIcon(props: IconProps) {
  return <IconBase {...props}><circle cx="5" cy="19" r="1" fill="currentColor" stroke="none" /><path d="M4 11a9 9 0 0 1 9 9M4 5a15 15 0 0 1 15 15" /></IconBase>;
}
