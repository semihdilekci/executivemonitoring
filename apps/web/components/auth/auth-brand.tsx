import { AppLogo } from "@/components/common/app-logo";

export function AuthBrand() {
  return (
    <div className="mb-8 text-center">
      <div className="mb-4 flex justify-center">
        <AppLogo size="lg" priority />
      </div>
      <p className="text-xs font-medium uppercase tracking-wider text-gray-500">
        Global Intelligence Platform
      </p>
    </div>
  );
}
