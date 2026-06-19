import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export default function NotFoundPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-bg px-4">
      <Card padding="lg" className="max-w-md text-center">
        <h1 className="text-2xl font-bold text-navy-800">Sayfa bulunamadı</h1>
        <p className="mt-2 text-sm text-gray-500">
          Aradığınız sayfa mevcut değil veya taşınmış olabilir.
        </p>
        <div className="mt-6">
          <Link href="/">
            <Button>Ana sayfaya dön</Button>
          </Link>
        </div>
      </Card>
    </div>
  );
}
