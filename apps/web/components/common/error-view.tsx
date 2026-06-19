import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ErrorViewProps {
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorView({
  message = "Veriler yüklenirken bir hata oluştu.",
  onRetry,
  className,
}: ErrorViewProps) {
  return (
    <div
      role="alert"
      className={cn(
        "rounded-xl border border-red-200 bg-red-50 px-6 py-8 text-center",
        className,
      )}
    >
      <p className="text-sm font-medium text-red-800">{message}</p>
      {onRetry ? (
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="mt-4"
          onClick={onRetry}
        >
          Tekrar Dene
        </Button>
      ) : null}
    </div>
  );
}
