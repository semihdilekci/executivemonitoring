import Image from "next/image";
import Link from "next/link";
import { cn } from "@/lib/utils";

const LOGO_SOURCES = {
  default: "/yildiz-holding-logo-transparent.png",
  light: "/yildiz-holding-logo-light.png",
} as const;

/** Kaynak görsel boyutu — en-boy oranı korunur. */
const LOGO_WIDTH = 1024;
const LOGO_HEIGHT = 83;

type AppLogoSize = "sm" | "md" | "lg";
type AppLogoVariant = keyof typeof LOGO_SOURCES;

const sizeConfig: Record<AppLogoSize, string> = {
  sm: "max-w-[120px]",
  md: "max-w-full",
  lg: "max-w-[240px]",
};

interface AppLogoProps {
  size?: AppLogoSize;
  variant?: AppLogoVariant;
  className?: string;
  href?: string;
  priority?: boolean;
}

export function AppLogo({
  size = "md",
  variant = "default",
  className,
  href = "/",
  priority = false,
}: AppLogoProps) {
  const wrapperClass = cn("block", sizeConfig[size], className);

  const image = (
    <Image
      src={LOGO_SOURCES[variant]}
      alt="Yıldız Holding"
      width={LOGO_WIDTH}
      height={LOGO_HEIGHT}
      priority={priority}
      className="h-auto w-full object-contain"
    />
  );

  if (!href) {
    return <span className={wrapperClass}>{image}</span>;
  }

  return (
    <Link href={href} className={wrapperClass} aria-label="Ana sayfa">
      {image}
    </Link>
  );
}
