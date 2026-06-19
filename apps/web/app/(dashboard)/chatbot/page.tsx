"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { ChatWindow } from "@/components/chatbot/chat-window";
import { PageLoadingSkeleton } from "@/components/common/loading-skeleton";

function ChatbotPageContent() {
  const searchParams = useSearchParams();
  const initialQuestion = searchParams.get("q");
  const digestId = searchParams.get("digest_id");

  return (
    <ChatWindow
      initialQuestion={initialQuestion}
      digestId={digestId}
    />
  );
}

export default function ChatbotPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-[calc(100dvh-10rem)]">
          <PageLoadingSkeleton />
        </div>
      }
    >
      <ChatbotPageContent />
    </Suspense>
  );
}
