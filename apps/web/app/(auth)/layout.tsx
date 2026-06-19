export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-navy-900 via-navy-800 to-navy-700 px-4 py-10">
      <div className="w-full max-w-md">{children}</div>
    </div>
  );
}
