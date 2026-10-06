import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Loader2 } from "lucide-react";

type Variant = "primary" | "secondary" | "outline" | "ghost";
type Size = "sm" | "md" | "lg";

const base =
  "group inline-flex items-center justify-center gap-2 rounded-full font-semibold whitespace-nowrap " +
  "transition-colors duration-150 focus-visible:outline-none focus-visible:shadow-ring " +
  "disabled:opacity-45 disabled:pointer-events-none";

const variants: Record<Variant, string> = {
  primary: "bg-indigo-700 text-white hover:bg-indigo-600 active:bg-indigo-900",
  secondary: "bg-mint-400 text-ink-900 hover:bg-mint-300",
  outline: "border border-indigo-700 text-indigo-700 bg-white hover:bg-indigo-50",
  ghost: "text-indigo-700 hover:underline underline-offset-4",
};

const sizes: Record<Size, string> = {
  sm: "h-9 px-4 text-sm",
  md: "h-11 px-6 text-[15px]",
  lg: "h-14 px-7 text-base",
};

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  arrow?: boolean;
  loading?: boolean;
  icon?: ReactNode;
  to?: string;
}

export function Button({
  variant = "primary",
  size = "md",
  arrow = false,
  loading = false,
  icon,
  to,
  className = "",
  children,
  disabled,
  ...rest
}: Props) {
  const cls = `${base} ${variants[variant]} ${sizes[size]} ${variant === "ghost" ? "!px-2" : ""} ${className}`;
  const trailing = loading ? (
    <Loader2 size={18} className="animate-spin" aria-hidden="true" />
  ) : arrow ? (
    <ArrowRight size={18} aria-hidden="true" className="transition-transform duration-150 group-hover:translate-x-1" />
  ) : null;
  const content = (
    <>
      {icon}
      {children}
      {trailing}
    </>
  );
  if (to) {
    return (
      <Link to={to} className={cls}>
        {content}
      </Link>
    );
  }
  return (
    <button className={cls} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {content}
    </button>
  );
}
