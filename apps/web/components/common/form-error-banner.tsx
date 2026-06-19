import { cn } from "@/lib/utils";

interface FormErrorBannerProps {
  message: string;
  className?: string;
}

export function FormErrorBanner({ message, className }: FormErrorBannerProps) {
  return (
    <div
      role="alert"
      className={cn(
        "rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700",
        className,
      )}
    >
      {message}
    </div>
  );
}
