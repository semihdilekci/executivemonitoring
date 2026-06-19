import { Suspense } from "react";
import { LoginForm } from "@/components/auth/login-form";
import { LoadingSkeleton } from "@/components/common/loading-skeleton";
import { Card } from "@/components/ui/card";

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <Card padding="lg">
          <LoadingSkeleton lines={5} />
        </Card>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
