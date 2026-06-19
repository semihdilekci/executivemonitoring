"use client";

import { ChatbotShortcut } from "@/components/home/chatbot-shortcut";
import { ExecutiveBrief } from "@/components/home/executive-brief";
import { UnreadTeasers } from "@/components/home/unread-teasers";

export default function HomePage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-navy-800">Ana Sayfa</h1>
        <p className="mt-1 text-sm text-gray-500">
          Günün özeti, okunmamış bültenler ve hızlı chatbot erişimi.
        </p>
      </div>

      <ExecutiveBrief />
      <UnreadTeasers />
      <ChatbotShortcut />
    </div>
  );
}
